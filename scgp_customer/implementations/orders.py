import logging
import random
from datetime import date, datetime

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, Sum, Value, When

from saleor.plugins.manager import get_plugins_manager
from sap_master_data import models as sap_master_data_models
from sap_migration import models as sap_migration_models
from sap_migration.graphql.enums import InquiryMethodType, OrderType
from scg_checkout.contract_create_order import get_weight_unit
from scg_checkout.contract_order_update import (
    get_tax_percent,
    is_order_contract_project_name_special,
)
from scg_checkout.graphql.enums import (
    ContractCheckoutErrorCode,
    SapOrderConfirmationStatus,
)
from scg_checkout.graphql.helper import (
    get_item_no_max_order_line,
    is_default_sale_unit_from_contract,
    is_materials_product_group_matching,
    update_order_product_group,
)
from scg_checkout.graphql.implementations.iplan import call_i_plan_create_order
from scg_checkout.graphql.implementations.orders import (
    get_material_variant_by_contract_product,
)
from scg_checkout.graphql.implementations.sap import sap_change_request_date
from scg_checkout.graphql.resolves.orders import (
    resolve_bill_to_address,
    resolve_ship_to_address,
)
from scgp_customer import models
from scgp_customer.graphql.enums import ScgpCustomerErrorCode, ScgpCustomerOrderStatus
from scgp_customer.models import CustomerOrderLine
from scgp_export.implementations.sap import get_web_user_name


def bulk_update_customer_order_lines(lines):
    return sap_migration_models.OrderLines.objects.bulk_update(
        [
            sap_migration_models.OrderLines(
                id=line.get("id"),
                quantity=line.get("quantity"),
                request_date=line.get("request_date"),
                total_weight=line.get("total_weight"),
                total_price=line.get("total_price"),
                original_request_date=line.get("original_request_date"),
            )
            for line in lines
        ],
        [
            "quantity",
            "request_date",
            "total_weight",
            "total_price",
            "original_request_date",
        ],
        batch_size=100,
    )


def validate_order(order_id, user):
    order = sap_migration_models.Order.objects.get(id=order_id)
    if order.status == ScgpCustomerOrderStatus.CONFIRMED.value:
        raise Exception("Confirmed order can not change status!")

    if not order:
        raise Exception(f"Order with id {order_id} not found!")

    if user != order.created_by:
        raise Exception("Can not update other's order!")

    return order


def pre_save(order):
    if (
        sap_migration_models.OrderLines.objects.filter(
            order_id=order.id, request_date__isnull=True
        ).count()
        != 0
    ):
        raise Exception("Some order lines are missing request delivery date!")

    if (
        not order.order_date
        or not order.order_no
        or not order.request_date
        or not order.ship_to
        or not order.bill_to
    ):
        raise Exception("Some fields are missing!")

    return True


def validate_lines_quantity(order_id, user, contract_product_ids):
    lines = sap_migration_models.OrderLines.objects.filter(
        order_id=order_id, order__created_by=user
    )

    if contract_product_ids:
        lines = lines.filter(contract_material_id__in=contract_product_ids)
    total_weight_field = DecimalField(max_digits=10, decimal_places=3)
    contract_products = (
        lines.values("contract_material")
        .order_by("contract_material")
        .annotate(
            sum_quantity=Case(
                When(total_weight__isnull=False, then=Sum(F("weight") * F("quantity"))),
                default=Value(0.0),
                output_field=total_weight_field,
            )
        )
        .filter(sum_quantity__gt=F("contract_material__remaining_quantity"))
    )
    contract_product_ids = [
        contract_product.get("contract_product")
        for contract_product in contract_products
    ]
    if len(contract_product_ids):
        invalid_quantity_line_ids = sap_migration_models.OrderLines.objects.filter(
            order_id=order_id,
            order__created_by=user,
            contract_material_id__in=contract_product_ids,
        ).values_list("id", flat=True)
        return invalid_quantity_line_ids
    return []


def combine_two_product_lists(list1, list2):
    combined_list = []
    for product1 in list1:
        for product2 in list2:
            if str(product2.get("contract_product_id")) == str(
                product1.get("contract_product_id")
            ) and str(product2.get("variant_id")) == str(product1.get("variant_id")):
                combined_list.append(
                    {
                        "contract_product_id": product2.get("contract_product_id"),
                        "variant_id": product2.get("variant_id"),
                    }
                )

    return combined_list


@transaction.atomic
def update_customer_order(order_id, order_information, info):
    try:
        logging.info(
            f" [Create customer order] For Order id: {order_id} , FE request payload: {order_information}"
            f" by user: {info.context.user} "
        )
        order = validate_order(order_id, info.context.user)
        today = date.today()
        request_delivery_date = order_information.get(
            "request_delivery_date", order.request_date
        )
        if request_delivery_date is not None and request_delivery_date < today:
            raise ValidationError(
                {
                    "request_date": ValidationError(
                        "Request date must be further than today",
                        code=ScgpCustomerErrorCode.INVALID.value,
                    )
                }
            )
        order.order_date = order_information.get("order_date", order.order_date)
        order.order_no = order_information.get("order_no", order.order_no)
        order.po_number = order_information.get("order_no", order.order_no)
        order.request_date = request_delivery_date
        order.ship_to = order_information.get("ship_to", order.ship_to)
        order.bill_to = order_information.get("bill_to", order.bill_to)
        order.unloading_point = order_information.get(
            "unloading_point", order.unloading_point
        )
        order.remark_for_invoice = order_information.get(
            "remark_for_invoice", order.remark_for_invoice
        )
        order.po_date = order_information.get("order_date", order.order_date)
        # TODO: use internal comments to logistic field
        order.remark_for_logistic = order_information.get(
            "remark_for_logistic", order.remark_for_logistic
        )
        order.internal_comments_to_warehouse = order_information.get(
            "internal_comments_to_warehouse", order.internal_comments_to_warehouse
        )
        order.internal_comments_to_logistic = order_information.get(
            "internal_comments_to_logistic", order.internal_comments_to_logistic
        )
        success = True
        sap_order_messages = []
        sap_item_messages = []
        i_plan_messages = []
        warning_messages = []
        if order_information.get("confirm", False) and pre_save(order):
            invalid_quantity_line_ids = validate_lines_quantity(
                order_id, info.context.user, []
            )
            if invalid_quantity_line_ids:
                raise ValueError(
                    f"Total weight of lines {','.join(str(e) for e in list(invalid_quantity_line_ids))} are greater than total remain "
                )
            # Removed due to cancel ticket SEO-1110
            # save_sale_employee_partner_data(order=order, plugin=info.context.plugins)
            order.web_user_name = get_web_user_name(
                order_type=OrderType.DOMESTIC, user=info.context.user
            )

            if is_order_contract_project_name_special(order):
                sap_migration_models.OrderLines.objects.filter(order=order).update(
                    remark="C1"
                )
            # order.status = ScgpCustomerOrderStatus.CONFIRMED.value
            response = call_i_plan_create_order(
                order, info.context.plugins, user=info.context.user
            )
            if response.get("success"):
                order.status = response.get("order_status")
                order.so_no = response.get("sap_order_number")
            else:
                success = False
            order.status_sap = response.get("sap_order_status")
            sap_order_messages = response.get("sap_order_messages")
            sap_item_messages = response.get("sap_item_messages")
            i_plan_messages = response.get("i_plan_messages")
            warning_messages = response.get("warning_messages")
        order.updated_at = datetime.now

        # Rollback when call API fail
        if success:
            order.save()
            deduct_cart_item(order)

        return (
            order,
            success,
            sap_order_messages,
            sap_item_messages,
            i_plan_messages,
            warning_messages,
            False,
            None,
        )
    except ValidationError as e:
        logging.info(
            f" [Create customer order] ValidationError {e} while creating Customer order for Order id: {order.id}"
            f" by user: {info.context.user}"
        )
        return (
            order,
            success,
            sap_order_messages,
            sap_item_messages,
            i_plan_messages,
            warning_messages,
            True,
            e,
        )

    except Exception as e:
        logging.info(
            f" [Create customer order] Exception {e} while creating Customer order for Order id: {order.id}"
            f" by user: {info.context.user}"
        )
        transaction.set_rollback(True)
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)


@transaction.atomic
def update_customer_order_lines(order_id, params, user):
    try:
        logging.info(
            f"[customer Create order] update_customer_order_lines order id: {order_id}, FE request :{params}"
        )
        apply_all = params.get("apply_all", False)
        order = validate_order(order_id, user)
        today = date.today()
        if apply_all:
            request_delivery_date = params.get("request_delivery_date")
            if request_delivery_date is not None and request_delivery_date < today:
                raise ValidationError(
                    {
                        "request_date": ValidationError(
                            "Request date must be further than today",
                            code=ScgpCustomerErrorCode.INVALID.value,
                        )
                    }
                )
            sap_migration_models.OrderLines.objects.filter(order_id=order_id).update(
                request_date=request_delivery_date
            )

            order.request_date = request_delivery_date
            order.updated_at = datetime.now
            order.save()

        lines = params.get("lines", [])
        if lines:
            line_ids = [line.get("id") for line in lines]
            line_objects = {}
            contract_product_ids = []
            for line in sap_migration_models.OrderLines.objects.filter(pk__in=line_ids):
                line_objects[str(line.id)] = line
                contract_product_ids.append(line.contract_material_id)

            bulk_update_lines = []
            for line in lines:
                line_id = str(line.get("id"))
                quantity = float(line.get("quantity", line_objects[line_id].quantity))
                request_delivery_date = line.get(
                    "request_delivery_date", line_objects[line_id].request_date
                )
                if request_delivery_date is not None and request_delivery_date < today:
                    raise ValidationError(
                        {
                            "request_date": ValidationError(
                                "Request date must be further than today",
                                code=ScgpCustomerErrorCode.INVALID.value,
                            )
                        }
                    )
                line = {
                    "id": line.get("id"),
                    "quantity": quantity,
                    "request_date": request_delivery_date,
                    "total_weight": float(quantity)
                    * float(line_objects[line_id].weight),
                    "total_price": float(quantity)
                    * float(line_objects[line_id].price_per_unit),
                    "original_request_date": request_delivery_date,
                }
                bulk_update_lines.append(line)

            bulk_update_customer_order_lines(bulk_update_lines)
            invalid_quantity_line_ids = validate_lines_quantity(
                order_id, user, contract_product_ids
            )
            if invalid_quantity_line_ids:
                raise ValueError(
                    f"Total weight of lines {','.join(str(e) for e in list(invalid_quantity_line_ids))} are greater than total remain "
                )

            return sync_order_prices(order_id)
        return order
    except Exception as e:
        logging.info(
            f"[Customer create order] Exception while updating_customer_order_lines: {e}"
        )
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


@transaction.atomic
def delete_customer_order_lines(ids, delete_all, order_id, user):
    try:
        if delete_all:
            validate_order(order_id, user)
            if not order_id:
                raise Exception("order_id is required when delete all")

            sap_migration_models.OrderLines.objects.filter(
                order_id=order_id, order__created_by=user
            ).delete()

        else:
            lines = sap_migration_models.OrderLines.objects.filter(
                id__in=ids, order__created_by=user
            )
            if lines.count() != len(ids):
                raise Exception("you dont have permission to delete other's order line")

            if not lines.count():
                return True

            order_id = lines.first().order_id
            validate_order(order_id, user)
            lines.delete()

        update_item_no(order_id, user)
        sync_order_prices(order_id)

        return True
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


@transaction.atomic
def add_products_to_order(order_id, products, user):
    try:
        order = validate_order(order_id, user)
        contract_product_ids = []
        variant_ids = []
        order_lines_i_plan = []
        for product in products:
            contract_product_ids.append(product.get("contract_product_id", None))
            variant_ids.append(product.get("variant_id", None))

        material_variant_objects = (
            sap_migration_models.MaterialVariantMaster.objects.filter(
                id__in=variant_ids
            ).in_bulk(field_name="id")
        )
        contract_product_objects = sap_migration_models.ContractMaterial.objects.filter(
            id__in=contract_product_ids
        ).in_bulk(field_name="id")

        material_variant_codes = list(
            sap_migration_models.MaterialVariantMaster.objects.filter(
                id__in=variant_ids
            ).values_list("code", flat=True)
        )

        conversion_objects = (
            sap_master_data_models.Conversion2Master.objects.filter(
                material_code__in=material_variant_codes,
                to_unit="ROL",
            )
            .distinct("material_code")
            .in_bulk(field_name="material_code")
        )

        bulk_create_lines = []
        max_item_no = get_item_no_max_order_line(order_id)
        max_item_no = max_item_no or 0
        item_no = int(max_item_no) + 10
        weight = 0
        price_per_unit = 0
        total_price = 0
        contract_materials = list(contract_product_objects.values())
        product_group = order.product_group
        if not is_materials_product_group_matching(
            product_group, contract_materials, order.type
        ):
            raise ValidationError(
                {
                    "product_group": ValidationError(
                        "Please select the same product group to create an order",
                        code=ScgpCustomerErrorCode.PRODUCT_GROUP_ERROR.value,
                    )
                }
            )
        if not max_item_no:
            product_group = contract_materials[0].mat_group_1
            update_order_product_group(order_id, product_group)
        for product in products:
            contract_product_id = product.get("contract_product_id", "")
            variant_id = product.get("variant_id", "")
            if not variant_id:
                variant_id = get_material_variant_by_contract_product(
                    contract_product_objects, contract_product_id
                )
            quantity = float(product.get("quantity", 0))

            contract_product_object = contract_product_objects.get(
                int(contract_product_id), None
            )
            material_variant_object = material_variant_objects.get(
                int(variant_id), None
            )
            material_variant_code = (
                material_variant_object.code if material_variant_object else None
            )

            conversion_object = conversion_objects.get(str(material_variant_code), None)

            if not contract_product_object:
                raise Exception(
                    f"Contract product with id: {contract_product_id} not found"
                )

            if conversion_object:
                calculation = conversion_object.calculation
                weight = float(calculation) / 1000

            price_per_unit = float(contract_product_object.price_per_unit) * weight
            total_price = quantity * price_per_unit * weight

            sales_unit = (
                contract_product_object.weight_unit or "TON"
                if is_default_sale_unit_from_contract(product_group)
                else "ROL"
            )
            i_plan = sap_migration_models.OrderLineIPlan()
            order_lines_i_plan.append(i_plan)
            line = sap_migration_models.OrderLines(
                order_id=order_id,
                item_no=item_no,
                contract_material_id=contract_product_id,
                material_variant_id=variant_id,
                material_id=contract_product_object.material_id,
                quantity=quantity,
                quantity_unit=contract_product_object.quantity_unit,
                weight=weight,
                total_weight=weight * quantity,
                price_per_unit=price_per_unit,
                total_price=total_price,
                net_price=total_price,
                inquiry_method=InquiryMethodType.CUSTOMER.value,
                sales_unit=sales_unit,
                ref_doc_it=contract_product_object.item_no,
                payment_term_item=contract_product_object.payment_term,
                iplan=i_plan,
            )
            bulk_create_lines.append(line)
            item_no += 10

        if len(bulk_create_lines):
            sap_migration_models.OrderLineIPlan.objects.bulk_create(order_lines_i_plan)
            sap_migration_models.OrderLines.objects.bulk_create(bulk_create_lines)

        invalid_quantity_line_ids = validate_lines_quantity(
            order_id, user, contract_product_ids
        )
        if invalid_quantity_line_ids:
            lines = sap_migration_models.OrderLines.objects.filter(
                id__in=invalid_quantity_line_ids
            ).values("contract_material_id", "variant_id")
            raise ValueError(
                f"Total weight of products {str(combine_two_product_lists(products, list(lines)))} are greater than total remain "
            )

        return sync_order_prices(order_id)
    except ValidationError as e:
        transaction.set_rollback(True)
        raise e
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


# update total_price, total_price_inc_tax, tax_amount when order lines change
def sync_order_prices(order_id):
    order = sap_migration_models.Order.objects.filter(id=order_id).first()
    if order:
        line_total_prices = sap_migration_models.OrderLines.objects.filter(
            order_id=order_id
        ).values_list("total_price", flat=True)
        total_price = sum(line_total_prices)
        tax_percent = get_tax_percent(order.sold_to.sold_to_code)
        tax_amount = float(total_price) * tax_percent
        order.total_price = float(total_price)
        order.tax_amount = tax_amount
        order.total_price_inc_tax = float(total_price) + tax_amount
        order.updated_at = datetime.now
        order.save()

    return order


def update_item_no(order_id, user):
    item_no = 10
    bulk_update_lines = []
    lines = sap_migration_models.OrderLines.objects.order_by("id").filter(
        order_id=order_id, order__created_by=user
    )
    for line in lines:
        line.item_no = item_no
        item_no += 10
        bulk_update_lines.append(line)
    if not lines:
        update_order_product_group(order_id, None)
    sap_migration_models.OrderLines.objects.bulk_update(bulk_update_lines, ["item_no"])


@transaction.atomic
def create_customer_order(params, info):
    try:
        sales_organization = None
        distribution_channel = None
        division = None
        sales_group = None
        sales_office = None
        unloading_point = None
        incoterms_id = None

        order_data, order_lines_data = handle_order_data(params)
        contract = sap_migration_models.Contract.objects.get(
            id=order_data.get("contract").id
        )
        if contract:
            sales_organization = contract.sales_organization
            distribution_channel = contract.distribution_channel
            division = contract.division
            sales_group = contract.sales_group
            sales_office = contract.sales_office
            unloading_point = contract.unloading_point
            if contract.incoterm:
                incoterm_obj = sap_master_data_models.Incoterms1Master.objects.filter(
                    code=contract.incoterm
                ).last()
                incoterms_id = incoterm_obj.id if incoterm_obj else None

        contract_currency = (
            sap_migration_models.ContractMaterial.objects.filter(
                contract=order_data.get("contract")
            )
            .first()
            .currency
        )
        currency = sap_master_data_models.CurrencyMaster.objects.filter(
            code=contract_currency
        ).first()
        contract_materials = []
        for order_lines in order_lines_data:
            contract_materials.append(order_lines.get("contract_product"))
        if not is_materials_product_group_matching(
            None, contract_materials, order_data.get("type")
        ):
            raise ValidationError(
                {
                    "product_group": ValidationError(
                        "Please select the same product group to create an order",
                        code=ContractCheckoutErrorCode.PRODUCT_GROUP_ERROR.value,
                    )
                }
            )
        product_group = contract_materials[0].mat_group_1

        order = sap_migration_models.Order.objects.create(
            contract=order_data.get("contract"),
            total_price=order_data.get("total_price"),
            total_price_inc_tax=order_data.get("total_price_inc_tax"),
            tax_amount=order_data.get("tax_amount"),
            status=order_data.get("status"),
            order_date=order_data.get("order_date"),
            created_by=info.context.user,
            created_at=order_data.get("created_at"),
            updated_at=order_data.get("updated_at"),
            type=order_data.get("type"),
            # mock so_no
            so_no=f"{int(datetime.now().timestamp() * 2 / 100)}",
            po_no=f"KPO0{int(datetime.now().timestamp() * 2 / 1_000_000)}",
            po_number=f"KPO0{int(datetime.now().timestamp() * 2 / 1_000_000)}",
            currency=currency,
            payment_term=contract.payment_term_key + " - " + contract.payment_term,
            sold_to=contract.sold_to,
            sales_organization=sales_organization,
            distribution_channel=distribution_channel,
            division=division,
            sales_group=sales_group,
            sales_office=sales_office,
            unloading_point=unloading_point,
            incoterms_1_id=incoterms_id,
            internal_comments_to_warehouse=contract.internal_comments_to_warehouse
            or "",
            internal_comments_to_logistic=contract.internal_comments_to_logistic or "",
            po_date=order_data.get("order_date"),
            product_group=product_group,
        )

        # save shipTo party and billTo party into order
        ship_to_address = resolve_ship_to_address(order, info)
        bill_to_address = resolve_bill_to_address(order, info)
        ship_to = contract.ship_to
        bill_to = contract.bill_to
        ship_to_party = f"{ship_to}\n{ship_to_address}" if ship_to else ""
        bill_to_party = f"{bill_to}\n{bill_to_address}" if bill_to else ""
        order.ship_to = ship_to_party
        order.bill_to = bill_to_party
        order.save()

        order_lines = []
        item_no = 10
        order_lines_i_plan = []
        for index, order_line in enumerate(order_lines_data):
            i_plan = sap_migration_models.OrderLineIPlan()
            order_lines_i_plan.append(i_plan)
            line = sap_migration_models.OrderLines(
                order=order,
                contract_material=order_line.get("contract_product"),
                material_variant=order_line.get("variant"),
                material=order_line.get("material"),
                quantity=order_line.get("quantity"),
                quantity_unit=order_line.get("quantity_unit"),
                weight=order_line.get("weight_per_unit"),
                total_weight=order_line.get("total_weight"),
                # TODO: migrate this to total_weight
                net_weight=order_line.get("total_weight"),
                price_per_unit=order_line.get("price_per_unit"),
                total_price=order_line.get("total_price"),
                net_price=order_line.get("net_price"),
                cart_item=order_line.get("cart_item"),
                item_no=item_no + (index * item_no),
                sap_confirm_status=random.choice(
                    SapOrderConfirmationStatus.SAP_ORDER_CONFIRMATION_STATUS_LIST.value
                ),
                iplan=i_plan,
                sales_unit=order_line.get("variant").sales_unit,
                inquiry_method=InquiryMethodType.DOMESTIC.value,
                ref_doc_it=order_line.get("contract_product").item_no
                if order_line.get("contract_product")
                else None,
                # plant=order_line.get("contract_product").plant
                # if order_line.get("contract_product")
                # else None,
                payment_term_item=order_line.get("contract_product").payment_term,
            )
            order_lines.append(line)
        sap_migration_models.OrderLineIPlan.objects.bulk_create(order_lines_i_plan)
        sap_migration_models.OrderLines.objects.bulk_create(order_lines)

        return order
    except ValidationError as e:
        transaction.set_rollback(True)
        raise e
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def handle_order_data(params):
    """
    Validate and handle data for order
    return dict order_data and list order_lines_data
    """
    lines = params.get("lines")
    order_information = params.pop("order_information")
    contract_id = order_information.get("contract_id")
    contract = sap_migration_models.Contract.objects.get(id=contract_id)

    if not contract:
        raise ValidationError(
            {
                "contract_id": ValidationError(
                    "Contract don't exist", ScgpCustomerErrorCode.NOT_FOUND.value
                )
            }
        )

    total_price = 0
    order_lines_data = []

    variants = sap_migration_models.MaterialVariantMaster.objects.filter(
        pk__in=(order_line.variant_id for order_line in lines)
    )
    dict_variant = {str(variant.id): variant for variant in variants}

    weights = get_weight_customer_from_variant(variants)

    for line in lines:
        contract_product_id = line.get("contract_product_id")
        variant_id = line.get("variant_id")
        quantity = line.get("quantity")
        cart_item_id = line.get("cart_item_id")
        # Get and validate contract product
        contract_product = sap_migration_models.ContractMaterial.objects.get(
            id=contract_product_id
        )
        if not contract_product:
            raise ValidationError(
                {
                    "lines": ValidationError(
                        f"Contract product {contract_product_id} don't exist",
                        ScgpCustomerErrorCode.NOT_FOUND.value,
                    )
                }
            )

        # Get and validate variant
        variant = sap_migration_models.MaterialVariantMaster.objects.get(id=variant_id)
        if not variant:
            raise ValidationError(
                {
                    "lines": ValidationError(
                        f"Variant {variant_id} don't exist",
                        ScgpCustomerErrorCode.NOT_FOUND.value,
                    )
                }
            )
        # Get and validate cart item
        cart_item = sap_migration_models.CartLines.objects.filter(
            id=cart_item_id
        ).first()
        # Calc total price of order
        weight = weights.get(dict_variant.get(str(line.variant_id)).code, 1)
        price_per_unit = contract_product.price_per_unit * weight
        total_price += quantity * contract_product.price_per_unit
        # Add order line info
        order_lines_data.append(
            {
                "variant": variant,
                "contract_product": contract_product,
                "quantity": quantity,
                "quantity_unit": contract_product.quantity_unit,
                "weight_per_unit": weight,
                "total_weight": quantity * weight,
                "net_price": weight * price_per_unit * quantity,
                "price_per_unit": price_per_unit,
                "total_price": quantity * price_per_unit * weight,
                "cart_item": cart_item,
                "item_no": contract_product.item_no,
                "material": variant.material,
            }
        )

    tax = get_tax_percent(contract.sold_to.sold_to_code)
    tax_amount = total_price * tax

    now = datetime.now()
    order_data = {
        "contract": contract,
        "total_price": total_price,
        "total_price_inc_tax": total_price + tax_amount,
        "tax_amount": tax_amount,
        "status": ScgpCustomerOrderStatus.DRAFT.value,
        "order_date": now,
        "created_at": now,
        "updated_at": now,
        "type": OrderType.CUSTOMER.value,
    }

    return order_data, order_lines_data


def deduct_quantity_cart_item(order_id, user):
    customer_order_lines = CustomerOrderLine.objects.filter(
        order_id=order_id, order__created_by=user
    )
    cart_ids = []
    for order_line in customer_order_lines:
        cart_item = order_line.cart_item
        if not cart_item:
            continue
        cart_item_quantity = cart_item.quantity
        order_line_quantity = order_line.quantity

        if cart_item_quantity > order_line_quantity:
            item_quantity = cart_item_quantity - order_line_quantity
            cart_item.quantity = item_quantity
            cart_item.save()
        else:
            cart_ids.append(cart_item.cart_id)
            cart_item.delete()

    if len(cart_ids):
        models.CustomerCart.objects.filter(id__in=cart_ids).annotate(
            total_item=Count("customercartitem")
        ).filter(total_item=0).delete()


def update_request_date_iplan(order_line_ids):
    order_lines = (
        sap_migration_models.OrderLines.objects.filter(id__in=order_line_ids)
        .annotate(order_so_no=F("order__so_no"))
        .all()
    )
    lines = []
    for order_line in order_lines:
        req_date = order_line.request_date
        confirmed_date = order_line.confirmed_date
        if req_date != confirmed_date:
            lines.append(order_line)
    if not lines:
        raise ValueError("No order line need to update")
    manager = get_plugins_manager()
    (es_21_sap_response_success, *_) = sap_change_request_date(lines, manager)
    if not es_21_sap_response_success:
        raise ValueError("SAP update order failed")
    for order_line in lines:
        order_line.request_date = order_line.confirmed_date
        order_line.save()
    return True


def deduct_cart_item(order):
    order_lines = sap_migration_models.OrderLines.objects.filter(order=order)
    cart_item_ids = []
    cart_id = None
    for order_line in order_lines:
        cart_item = order_line.cart_item
        cart_item_id = order_line.cart_item_id
        cart_item_ids.append(cart_item_id)
        if cart_item:
            cart_id = cart_item.cart_id

    if len(cart_item_ids):
        sap_migration_models.CartLines.objects.filter(id__in=cart_item_ids).delete()
        sap_migration_models.Cart.objects.filter(id=cart_id).annotate(
            num_cart_lines=Count("cartlines")
        ).filter(num_cart_lines=0).delete()


def get_weight_customer_from_variant(variants):
    result = {}
    list_material = list(map(lambda x: x.code, variants))
    conversions = (
        sap_master_data_models.Conversion2Master.objects.filter(
            material_code__in=map(lambda x: x, list_material), to_unit="ROL"
        )
        .values("material_code", "calculation")
        .all()
    )

    dict_material = {}
    for conversion in conversions:
        dict_material[conversion["material_code"]] = conversion["calculation"]

    for material in list_material:
        result[material] = (
            get_weight_unit(dict_material[material])
            if dict_material.get(material)
            else 1
        )

    return result
