import logging
import uuid

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import Q

import scg_checkout.contract_order_update as fn
from common.iplan.item_level_helpers import get_product_code
from sap_master_data import models as sap_master_data_models
from sap_migration.graphql.enums import InquiryMethodType
from sap_migration.models import (
    ContractMaterial,
    MaterialVariantMaster,
    Order,
    OrderLines,
)
from scg_checkout.graphql.enums import IPlanOrderItemStatus
from scg_checkout.graphql.helper import update_order_status
from scg_checkout.graphql.implementations.change_order import get_iplan_error_messages
from scg_checkout.graphql.implementations.iplan import (
    change_parameter_follow_inquiry_method,
)
from scg_checkout.graphql.implementations.orders import (
    call_es21_to_undo_orderlines,
    call_i_plan_request,
    call_iplan_confirm_undo,
    call_iplan_roll_back,
    update_iplan_for_order_line,
    update_item_status_for_special_container_items,
    validate_order,
)
from scg_checkout.graphql.implementations.sap import (
    get_error_messages_from_sap_response_for_change_order,
)
from scgp_export.error_codes import ScgpExportErrorCode
from scgp_export.graphql.enums import (
    ItemCat,
    MaterialGroup,
    ScgExportOrderLineAction,
    ScgpExportOrderStatus,
)
from scgp_require_attention_items.graphql.helper import update_attention_type_r5

from .orders import (
    update_remaining_quantity_pi_product_for_completed_order,
    validate_lines_quantity,
)


@transaction.atomic
def add_product_to_order(order_id, products, user):
    try:
        order = validate_order(order_id)
        pi_product_ids = [product.get("pi_product", "") for product in products]
        sales_organization_code = (
            order.sales_organization.code if order.sales_organization else None
        )
        distribution_channel_code = (
            order.distribution_channel.code if order.distribution_channel else None
        )
        sold_to_code = order.sold_to.sold_to_code
        tax_percent = fn.get_tax_percent(sold_to_code)
        channel_master = sap_master_data_models.SoldToChannelMaster.objects.filter(
            sold_to_code=sold_to_code,
            sales_organization_code=sales_organization_code,
            distribution_channel_code=distribution_channel_code,
        ).first()
        material_codes = []
        pi_product_objects = {}
        material_ids = []

        for pi_product in ContractMaterial.objects.filter(id__in=pi_product_ids):
            pi_product_objects[str(pi_product.id)] = pi_product
            material_codes.append(pi_product.material.material_code)
            material_ids.append(pi_product.material.id)

        # Get all material variant of order
        dict_material_variants = {}
        qs_material_materials = (
            MaterialVariantMaster.objects.filter(material_id__in=material_ids)
            .order_by("material_id", "id")
            .distinct("material_id")
        )
        for material_variant in qs_material_materials:
            dict_material_variants[str(material_variant.material_id)] = material_variant

        conversion_objects = (
            sap_master_data_models.Conversion2Master.objects.filter(
                material_code__in=material_codes,
                to_unit="ROL",
            )
            .order_by("material_code", "-id")
            .distinct("material_code")
            .in_bulk(field_name="material_code")
        )

        material_classification_master_objects = (
            sap_master_data_models.MaterialClassificationMaster.objects.filter(
                material_code__in=material_codes,
            )
            .distinct("material_code")
            .in_bulk(field_name="material_code")
        )

        material_sale_master_objects = (
            sap_master_data_models.MaterialSaleMaster.objects.filter(
                material_code__in=material_codes,
                sales_organization_code=sales_organization_code,
                distribution_channel_code=distribution_channel_code,
            )
            .distinct("material_code")
            .in_bulk(field_name="material_code")
        )

        bulk_create_lines = []

        weight = 0
        for product in products:
            pi_product_id = product.get("pi_product", "")
            pi_product_object = pi_product_objects.get(str(pi_product_id), None)
            material_code = pi_product_object.material.material_code
            conversion_object = conversion_objects.get(str(material_code), None)
            material = pi_product_object.material

            if not pi_product_object:
                raise Exception(f"Contract product with id: {pi_product_id} not found")
            material_classification_master = material_classification_master_objects.get(
                str(material_code), None
            )
            material_sale_master = material_sale_master_objects.get(
                str(material_code), None
            )

            # Get variant of order line from above dict materials
            material_variant = dict_material_variants.get(str(material.id))
            if not material_variant:
                raise ValidationError(
                    {
                        "material_variant": ValidationError(
                            f"Contract material {product.get('pi_product')} don't have material variant.",
                            code=ScgpExportErrorCode.NOT_FOUND.value,
                        )
                    }
                )

            quantity = float(product.get("quantity", 0))
            if conversion_object:
                calculation = conversion_object.calculation
                weight = float(calculation) / 1000

            if order.status not in (
                ScgpExportOrderStatus.DRAFT.value,
                ScgpExportOrderStatus.PRE_DRAFT.value,
            ):
                update_remaining_quantity_pi_product_for_completed_order(
                    pi_product_object,
                    weight,
                    quantity,
                    ScgExportOrderLineAction.UPDATE.value,
                )

            net_price = weight * float(pi_product_object.price_per_unit)

            line = OrderLines(
                order=order,
                material=pi_product_object.material,
                material_code=pi_product_object.material.material_code,
                material_variant=material_variant,
                contract_material=pi_product_object,
                quantity=quantity,
                quantity_unit=pi_product_object.quantity_unit,
                weight=weight,
                weight_unit=pi_product_object.weight_unit,
                total_weight=weight * quantity,
                net_price=net_price,
                vat_percent=tax_percent * 100,
                commission_percent=pi_product_object.commission,
                commission_amount=pi_product_object.commission_amount,
                commission_unit=pi_product_object.com_unit,
                item_cat_eo=ItemCat.ZKC0.value
                if pi_product_object.material.material_group == MaterialGroup.PK00.value
                else "",
                delivery_tol_over=channel_master.over_delivery_tol
                if channel_master
                else None,
                delivery_tol_under=channel_master.under_delivery_tol
                if channel_master
                else None,
                delivery_tol_unlimited=False,
                roll_diameter=material_classification_master.diameter
                if material_classification_master
                else "",
                roll_core_diameter=material_classification_master.core_size
                if material_classification_master
                else "",
                roll_quantity=150,
                roll_per_pallet=300,
                pallet_size="NP",
                pallet_no="1-150",
                package_quantity=168,
                packing_list="1 ROLL x 151 PACKAGES DIMENSION (WxLxH):40'x40'x34'",
                shipping_point="",
                remark=pi_product_object.contract.shipping_mark,
                reject_reason=None,
                inquiry_method=InquiryMethodType.EXPORT.value,
                material_group2=f"{material_sale_master.material_group1} - {material_sale_master.material_group1_desc}"
                if material_sale_master
                else "",
                condition_group1=pi_product_object.condition_group1,
                ref_doc=pi_product_object.contract_no or None,
                ref_doc_it=pi_product_object.item_no or None,
            )
            bulk_create_lines.append(line)
        invalid_quantity_line_ids = validate_lines_quantity(order.id, pi_product_ids)
        if invalid_quantity_line_ids:
            raise ValueError(
                f"Total weight of pi products {', '.join(str(line_id) for line_id in invalid_quantity_line_ids)}"
                f" are greater than total remaining "
            )
        return bulk_create_lines
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


@transaction.atomic
def undo_order_lines_export(data, info):
    success = True
    i_plan_messages_response = []
    sap_order_messages = []
    sap_item_messages = []
    params = {
        "DDQRequest": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQRequestHeader": [],
        }
    }
    # for one order line
    so_no = data["so_no"]
    item_no = data["item_no"]
    logging.info(
        f"[Export: Undo order lines]: For the Order {so_no} FE request: {data},"
        f"by user: {info.context.user}"
    )
    params, parameter = prepare_params_for_i_plan_export(params, so_no, item_no, "NEW")
    order = Order.objects.filter(so_no=so_no).first()
    order_line = (
        OrderLines.objects.select_related("iplan", "material_variant")
        .filter(order__so_no=so_no, item_no__in=item_no)
        .first()
    )
    params_for_es21 = prepare_params_for_es21_undo_export(so_no, order_line)
    scgp_user = info.context.user.scgp_user
    if scgp_user and scgp_user.sap_id:
        params_for_es21["sapId"] = scgp_user.sap_id
    # Only call iplan if order line was undo and has NOT special plant(SEO-4266)
    if not (has_special_plant(order_line) or order_line.item_cat_eo == "ZKC0"):
        logging.info("[Export: Undo order lines] calling.... iplan")
        response = call_i_plan_request(params, order=order)
        logging.info("[Export: Undo order lines] called iplan")
        i_plan_error_messages = get_iplan_error_messages(response)
        logging.info(
            f"[Export: Undo order lines]: i_plan_error_messages: {i_plan_error_messages}"
        )
        if i_plan_error_messages:
            success = False
            i_plan_messages_response = i_plan_error_messages
            return (
                success,
                i_plan_messages_response,
                sap_order_messages,
                sap_item_messages,
            )
    logging.info("[Export: Undo order lines] calling..... ES21")
    response_es21 = call_es21_to_undo_orderlines(params_for_es21, order)
    logging.info("[Export: Undo order lines] called ES21")

    (
        sap_order_messages,
        sap_item_messages,
        is_being_process,
        sap_success,
    ) = get_error_messages_from_sap_response_for_change_order(response_es21)

    if sap_order_messages or sap_item_messages:
        logging.info(
            f"[Export: Undo order lines]: sap_order_error_message: {sap_order_messages},"
            f"sap_item_error_messages: {sap_item_messages}"
        )
        success = False
        logging.info(
            "[Export: Undo order lines] calling iplan_roll_back as ES21 failed"
        )
        call_iplan_roll_back(data["so_no"].lstrip("0"), order_line)
        logging.info("[Export: Undo order lines] iplan_roll_back called")
        return (
            success,
            i_plan_messages_response,
            sap_order_messages,
            sap_item_messages,
        )
    if not (has_special_plant(order_line) or order_line.item_cat_eo == "ZKC0"):
        logging.info("[Export: Undo order lines]: calling iplan_confirm_commit")
        response_i_plan_confirm = call_iplan_confirm_undo(
            data["so_no"].lstrip("0"), order_line, response, response_es21
        )
        logging.info("[Export: Undo order lines]: iplan_confirm called")
        i_plan_error_messages = get_iplan_error_messages(response_i_plan_confirm)
        logging.info(
            f"[Export: Undo order lines]: i_plan_confirm_error_messages: {i_plan_error_messages}"
        )
        if i_plan_error_messages:
            update_attention_type_r5([order_line])
            i_plan_messages_response = i_plan_error_messages
            success = False
            return (
                success,
                i_plan_messages_response,
                sap_order_messages,
                sap_item_messages,
            )
        update_iplan_for_order_line(so_no, response, parameter)
    else:
        update_item_status_for_special_container_items(order_line)
    status_en, status_thai = update_order_status(order.id)
    logging.info(
        f"[Export: Undo order lines] DB order {order.so_no} status :{order.status} updated to {status_en}"
    )
    order.status = status_en
    order.status_thai = status_thai
    order.save()
    logging.info(
        f"[Export: Undo order lines] Undo item {item_no} of order with SoNo : {order.so_no} is completed successfully"
    )
    return (
        success,
        i_plan_messages_response,
        sap_order_messages,
        sap_item_messages,
    )


def prepare_params_for_i_plan_export(params, order_so_no, items_no, flag):
    param_order = {
        "headerCode": order_so_no.lstrip("0"),
        "autoCreate": False,
        "DDQRequestLine": [],
    }
    order = Order.objects.filter(so_no=order_so_no).first()
    order_lines = (
        OrderLines.objects.filter(
            order__so_no=order_so_no,
            item_no__in=items_no,
        )
        .exclude(
            Q(item_status_en=IPlanOrderItemStatus.CANCEL.value)
            | Q(
                item_status_th=IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
                    IPlanOrderItemStatus.CANCEL.value
                )
            )
        )
        .all()
    )
    if flag == "NEW":
        order_lines = OrderLines.objects.filter(
            order__so_no=order_so_no,
            item_no__in=items_no,
        ).first()

        # System should send inquiry method as default value = JITCP on YT65156/plan request when undo item
        # Ref. SEO-6071
        order_lines.inquiry_method = InquiryMethodType.EXPORT.value
        order_lines.save(update_fields=["inquiry_method"])

        result = prepare_for_ddq_request_line_export(order_lines, flag, order)
        request_line = result.get("request_line")
        parameter = result.get("parameter")
        param_order["DDQRequestLine"].append(request_line)
        params["DDQRequest"]["DDQRequestHeader"].append(param_order)
        return params, parameter

    for order_line in order_lines:
        param_order["DDQRequestLine"].append(
            prepare_for_ddq_request_line_export(order_line, flag, order).get(
                "request_line"
            )
        )
    params["DDQRequest"]["DDQRequestHeader"].append(param_order)
    return params


def prepare_for_ddq_request_line_export(order_line, flag, order):
    parameter = change_parameter_follow_inquiry_method(order_line, order, flag)
    fmt_sold_to_code = (
        order.sold_to and order.sold_to.sold_to_code or order.sold_to_code or ""
    ).lstrip("0") or None
    request_line = {
        "lineNumber": order_line.item_no.lstrip("0"),
        "locationCode": fmt_sold_to_code,
        "consignmentOrder": False,
        "productCode": get_product_code(order_line),
        "requestDate": order_line.request_date.strftime("%Y-%m-%dT00:00:00.000Z")
        if order_line.request_date
        else "",
        "inquiryMethod": parameter.get("inquiry_method"),
        "quantity": str(order_line.quantity),
        "unit": "ROL",
        "transportMethod": "Truck",
        "typeOfDelivery": "E",
        "useConsignmentInventory": parameter.get("use_consignment_inventory"),
        "useProjectedInventory": parameter.get("use_projected_inventory"),
        "useProduction": parameter.get("use_production"),
        "orderSplitLogic": parameter.get("order_split_logic").upper(),
        "useInventory": parameter.get("use_inventory"),
        "singleSourcing": parameter.get("single_source"),
        "reATPRequired": parameter.get("re_atp_required"),
        "fixSourceAssignment": "",
        "consignmentLocation": order.sales_group.code,
        "requestType": flag,
        "DDQSourcingCategories": [
            {"categoryCode": order.sales_organization.code or ""},
            {"categoryCode": order.sales_group.code or ""},
        ],
    }
    return {"request_line": request_line, "parameter": parameter}


def prepare_params_for_es21_undo_export(so_no, order_lines):
    order = Order.objects.filter(so_no=so_no).first()
    contract_code = ""
    if order.contract and order.contract.code:
        contract_code = order.contract.code
    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": so_no,
        "testrun": False,
        "orderHeaderIn": {
            "refDoc": contract_code,
        },
        "orderHeaderInX": {},
        "orderItemsIn": [],
        "orderItemsInx": [],
    }

    params["orderItemsIn"].append(
        {
            "itemNo": order_lines.item_no,
            "material": order_lines.material_variant.code
            if order_lines.material_variant
            else order_lines.material_code,
            "targetQty": order_lines.quantity,
            "salesUnit": "EA"
            if order_lines.item_cat_eo == ItemCat.ZKC0.value
            else "ROL",
            "reasonReject": "",
            "refDoc": order_lines.ref_doc if order_lines.ref_doc else "",
            "refDocIt": order_lines.contract_material
            and order_lines.contract_material.item_no
            or "",
        }
    )
    params["orderItemsInx"].append(
        {"itemNo": order_lines.item_no, "updateflag": "U", "reasonReject": True}
    )

    return params


def has_special_plant(order_line):
    if order_line.plant in ["754F", "7531", "7533"]:
        return True
    return False
