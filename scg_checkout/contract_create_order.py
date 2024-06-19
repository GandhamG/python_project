import random
from datetime import datetime

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction

import sap_master_data.models
from common.helpers import net_price_calculation
from common.product_group import ProductGroup
from sap_master_data import models as master_models
from sap_migration import models as sap_migration_models
from sap_migration.graphql.enums import CreatedFlow, InquiryMethodType, OrderType
from sap_migration.models import Contract, ContractMaterial
from scg_checkout.error_codes import ContractCheckoutErrorCode
from scgp_export.graphql.resolvers.orders import resolve_get_credit_limit

from .graphql.enums import (
    PaymentTerm,
    ScgDomesticOrderType,
    ScgOrderStatus,
    UnitEnum,
    WeightUnitEnum,
)
from .graphql.helper import (
    is_default_sale_unit_from_contract,
    is_materials_product_group_matching,
    is_other_product_group,
)
from .graphql.resolves.customer_block import resolve_get_customer_block
from .graphql.resolves.orders import build_ship_to_party, resolve_bill_to_address


def get_weigh_from_checkout_lines(checkout_lines):
    result = {}
    list_material = list(
        map(lambda x: (x.material_id, x.material.material_code), checkout_lines)
    )
    conversions = (
        master_models.Conversion2Master.objects.filter(
            material_code__in=map(lambda x: x[1], list_material), to_unit="ROL"
        )
        .values("material_code", "calculation")
        .all()
    )
    for i, material in enumerate(list_material):
        calculation = 0
        if len(conversions) > i:
            calculation = get_weight_unit(conversions[i]["calculation"])
        result[material[0]] = calculation
    return result


def get_weigh_domestic_from_checkout_lines(checkout_lines):
    result = {}
    list_material = list(map(lambda x: x.material_variant.code, checkout_lines))
    conversions = (
        master_models.Conversion2Master.objects.filter(
            material_code__in=list_material, to_unit="ROL"
        )
        .order_by("material_code", "-id")
        .distinct("material_code")
        .values("material_code", "calculation")
        .all()
    )

    for conversion in conversions:
        calculation = get_weight_unit(conversion["calculation"])
        result[conversion["material_code"]] = calculation

    return result


def get_weigh_by_sale_unit_from_checkout_lines(checkout_lines):
    result = {}
    list_material = list(map(lambda x: x.material_variant.code, checkout_lines))
    conversions = (
        master_models.Conversion2Master.objects.filter(material_code__in=list_material)
        .order_by("material_code", "-id")
        .distinct("material_code")
        .values("material_code", "calculation", "to_unit")
        .all()
    )

    material_unit_dict = {
        line.material_variant.code: line.material_variant.sales_unit
        for line in checkout_lines
    }

    for conversion in conversions:
        sale_unit = material_unit_dict[conversion["material_code"]]
        if conversion["to_unit"] == sale_unit:
            calculation = get_weight_unit(conversion["calculation"])
            result[conversion["material_code"]] = calculation

    return result


def get_weight_unit(calculation):
    if not calculation:
        return 0
    return float(calculation) / 1000


def default_order_type_product_group(product_group):
    if product_group in ProductGroup.get_product_group_1().value:
        return False
    return True


def get_plant_by_product_group_from_checkout_lines(checkout_lines):
    result = {}
    material_codes = [line.material_variant.code for line in checkout_lines]

    plant_details = (
        ContractMaterial.objects.filter(material_code__in=material_codes)
        .order_by("material_code", "-id")
        .distinct("material_code")
        .values("material_code", "plant")
        .all()
    )
    result = {data["material_code"]: data["plant"] for data in plant_details}

    return result


@transaction.atomic
def contract_create_order(info, params):
    try:

        order_lines_info = params.pop("lines")
        order_information = params.pop("order_information")
        contract = Contract.objects.get(id=order_information.get("contract_id"))
        sales_organization = contract.sales_organization
        distribution_channel = contract.distribution_channel
        division = contract.division
        sales_group = contract.sales_group
        sales_office = contract.sales_office
        company = contract.company
        incoterms_1 = master_models.Incoterms1Master.objects.filter(
            code=contract.incoterm
        ).first()

        sold_to_id = order_information.get("customer_id")
        sold_to_code = (
            sap_master_data.models.SoldToMaster.objects.filter(id=sold_to_id)
            .first()
            .sold_to_code
        )
        checkout_line_ids = [
            order_line.checkout_line_id for order_line in order_lines_info
        ]

        checkout_lines = sap_migration_models.CartLines.objects.filter(
            pk__in=checkout_line_ids
        )
        checkout_line_objects = {}
        contract_ids = set()
        contract_materials = []
        for i, checkout_line in enumerate(checkout_lines):
            checkout_line_objects[str(checkout_line.id)] = checkout_line
            contract_id = checkout_line.contract_material.contract_id
            contract_materials.append(checkout_line.contract_material)
            if i == 0:
                contract_ids.add(contract_id)
                continue
            if contract_id not in contract_ids:
                raise ValidationError(
                    {
                        "contract_id": ValidationError(
                            "Cannot continue. Please select Material from the same Contract No.",
                            code=ContractCheckoutErrorCode.CONTRACT_ERROR.value,
                        )
                    }
                )
        if not is_materials_product_group_matching(
            None, contract_materials, OrderType.DOMESTIC.value
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

        # raise_error_if_customer_or_credit_blocked(
        #     info,
        #     {
        #         "contract_no": contract.code,
        #         "sold_to_code": sold_to_code,
        #         "sales_org_code": sales_organization.code,
        #     },
        # )

        external_comments_to_customer = contract.external_comments_to_customer
        product_information = contract.production_information
        internal_comments_to_warehouse = contract.internal_comments_to_warehouse
        internal_comments_to_logistic = contract.internal_comments_to_logistic
        contract_currency = (
            sap_migration_models.ContractMaterial.objects.filter(contract=contract)
            .first()
            .currency
        )
        currency = sap_master_data.models.CurrencyMaster.objects.filter(
            code=contract_currency
        ).first()

        order_type = None

        order_type = (
            ScgDomesticOrderType.ZBV.value
            if contract.payment_term_key == PaymentTerm.DEFAULT.value
            else ScgDomesticOrderType.ZOR.value
        )

        order = sap_migration_models.Order.objects.create(
            sold_to_id=sold_to_id,
            status=ScgOrderStatus.PRE_DRAFT.value,
            created_by=info.context.user,
            type=OrderType.DOMESTIC.value,
            contract_id=order_information.get("contract_id"),
            payment_term=contract.payment_term_key + " - " + contract.payment_term,
            currency=currency,
            # mock so_no
            so_no=f"{int(datetime.now().timestamp() * 2 / 100)}",
            internal_comments_to_warehouse=internal_comments_to_warehouse,
            internal_comments_to_logistic=internal_comments_to_logistic,
            external_comments_to_customer=external_comments_to_customer,
            product_information=product_information,
            sales_organization=sales_organization,
            distribution_channel=distribution_channel,
            division=division,
            sales_group=sales_group,
            sales_office=sales_office,
            # mock data from sap
            customer_group_1_id=1,
            customer_group_2_id=1,
            customer_group_3_id=1,
            customer_group_4_id=1,
            customer_group_id=1,
            dp_no=f"01{int(datetime.now().timestamp() * 2 / 100)}",
            invoice_no=f"01{int(datetime.now().timestamp())}",
            incoterms_1_id=incoterms_1.id or None,
            delivery_block=random.choice(["Block", "No Block"]),
            company=company,
            order_type=order_type,
            created_by_flow=CreatedFlow.DOMESTIC_EORDERING.value,
            product_group=product_group,
        )

        # save shipTo party and billTo party into order
        # order_id = order.id
        # ship_to_address = resolve_ship_to_address(order, info)
        bill_to_address = resolve_bill_to_address(order, info)
        # ship_to = remove_padding_zero_from_ship_to(contract.ship_to)
        bill_to = contract.bill_to
        # ship_to_party = f"{ship_to}\n{ship_to_address}" if ship_to else ""
        ship_to_party = build_ship_to_party(order, info)
        bill_to_party = f"{bill_to}\n{bill_to_address}" if bill_to else ""
        order.ship_to = ship_to_party
        order.bill_to = bill_to_party
        order.save()

        # mock i_plan data for order_lines
        order_lines = []
        item_no = 10

        if is_other_product_group(product_group):
            weights = get_weigh_by_sale_unit_from_checkout_lines(checkout_lines)
            plants = get_plant_by_product_group_from_checkout_lines(checkout_lines)
        else:
            weights = get_weigh_domestic_from_checkout_lines(checkout_lines)

        variant_ids = []
        for order_line in order_lines_info:
            variant_ids.append(order_line.get("variant_id"))
        qs_variants = sap_migration_models.MaterialVariantMaster.objects.filter(
            id__in=variant_ids
        )
        dict_variants = {}
        for variant in qs_variants:
            dict_variants[str(variant.id)] = variant

        channel_master = master_models.SoldToChannelMaster.objects.filter(
            sold_to_code=sold_to_code,
            sales_organization_code=sales_organization.code,
            distribution_channel_code=distribution_channel.code,
        ).first()
        for index, order_line in enumerate(order_lines_info):
            try:
                checkout_line = checkout_line_objects[str(order_line.checkout_line_id)]
            except KeyError:
                raise KeyError("Item doesn't exist in cart anymore!!")
            quantity = order_line.get("quantity", checkout_line.quantity)
            i_plans = sap_migration_models.OrderLineIPlan.objects.create(
                attention_type=None,
                atp_ctp=None,
                atp_ctp_detail=None,
                block=None,
                run=None,
                iplant_confirm_quantity=None,
                item_status=None,
                original_date=None,
                inquiry_method_code=None,
                transportation_method=None,
                type_of_delivery=None,
                fix_source_assignment=None,
                split_order_item=None,
                partial_delivery=None,
                consignment=None,
                paper_machine=None,
            )
            weight = weights.get(checkout_line.material_variant.code, 1)
            variant = dict_variants.get(order_line.get("variant_id"))
            plant = None
            if is_other_product_group(product_group) and plants:
                plant = plants.get(checkout_line.material_variant.code, None)

            # ES14 response sale unit is mapped to wcontract_material > weight_unit
            sale_unit = (
                (variant and variant.sales_unit)
                or checkout_line.contract_material.weight_unit
                or WeightUnitEnum.TON.value
                if is_default_sale_unit_from_contract(product_group)
                else UnitEnum.ROL.value
            )
            line = sap_migration_models.OrderLines(
                order_id=order.pk,
                prc_group_1=product_group,
                item_no=item_no + (index * item_no),
                po_no_external=random.randint(10000, 99999),
                po_no=order.po_no,
                material_id=checkout_line.material.id,
                material_variant=variant,
                contract_material_id=checkout_line.contract_material.id,
                plant=plant,
                quantity=quantity,
                original_quantity=quantity,
                net_price=net_price_calculation(
                    product_group,
                    quantity,
                    checkout_line.contract_material.price_per_unit,
                    weight,
                ),
                request_date=order_line.get("request_date", None),
                internal_comments_to_warehouse=order_line.get(
                    "internal_comments_to_warehouse", ""
                ),
                product_information=order_line.get("product_information", ""),
                cart_item_id=checkout_line.id,
                confirmed_date=None,
                type=OrderType.DOMESTIC.value,
                weight=weight,
                weight_unit=WeightUnitEnum.TON.value,
                total_weight=weight * quantity,
                price_per_unit=checkout_line.contract_material.price_per_unit,
                price_currency=checkout_line.contract_material.currency,
                iplan=i_plans,
                inquiry_method=InquiryMethodType.DOMESTIC.value,
                sales_unit=sale_unit,
                sap_confirm_status=None,
                ref_doc_it=checkout_line.contract_material.item_no,
                delivery_tol_over=channel_master.over_delivery_tol
                if channel_master
                else None,
                delivery_tol_under=channel_master.under_delivery_tol
                if channel_master
                else None,
                payment_term_item=checkout_line.contract_material.payment_term,
                ref_doc=order.contract.code,
                additional_remark=checkout_line.contract_material.additional_remark,
            )
            order_lines.append(line)
        sap_migration_models.OrderLines.objects.bulk_create(order_lines)

        return order
    except ValidationError as e:
        raise e
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


@transaction.atomic
def clone_order(order_id, created_by_id):
    try:
        order = sap_migration_models.Order.objects.get(pk=order_id)
        order.pk = None
        order.created_by_id = created_by_id
        order.save()

        order_lines = sap_migration_models.OrderLines.objects.filter(order_id=order_id)
        new_order_lines = list()
        for order_line in order_lines:
            order_line.pk = None
            order_line.order_id = order.id

            if order_line.iplan_id:
                new_order_line_iplan = sap_migration_models.OrderLineIPlan.objects.get(
                    pk=order_line.iplan_id
                )
                new_order_line_iplan.pk = None
                new_order_line_iplan.save()
                order_line.iplan_id = new_order_line_iplan.id

            new_order_lines.append(order_line)

        sap_migration_models.OrderLines.objects.bulk_create(new_order_lines)

        return order

    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def raise_error_if_customer_or_credit_blocked(info, data_input):
    credit_limit = resolve_get_credit_limit(info, data_input)
    customer_block = resolve_get_customer_block(
        data_input.get("sold_to_code"), data_input.get("contract_no")
    )
    if customer_block.get("customer_block") or credit_limit.get("credit_block_status"):
        raise ValidationError("Customer or Credit is blocked")
