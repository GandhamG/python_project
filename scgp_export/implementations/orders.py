import base64
import json
import logging
import random
import traceback
import uuid
from copy import deepcopy
from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import (
    Case,
    Count,
    DecimalField,
    F,
    IntegerField,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Cast

import sap_migration.models
import scg_checkout.contract_order_update as fn
from common.enum import MulesoftServiceType
from common.helpers import format_sap_decimal_values_for_pdf
from common.iplan.item_level_helpers import get_product_code
from common.mulesoft_api import MulesoftApiRequest
from common.product_group import SalesUnitEnum
from saleor.order import OrderStatus
from saleor.plugins.manager import get_plugins_manager
from sap_master_data import models as sap_master_data_models
from sap_master_data.models import SoldToTextMaster, SoldToUnloadingPointMaster
from sap_migration.graphql.enums import InquiryMethodType, OrderType
from sap_migration.models import (
    Cart,
    CartLines,
    Contract,
    ContractMaterial,
    MaterialVariantMaster,
    Order,
    OrderLineIPlan,
    OrderLines,
)
from scg_checkout.graphql.enums import (
    IPlanOrderItemStatus,
    IPLanResponseStatus,
    SapOrderConfirmationStatus,
    ScgOrderStatus,
)
from scg_checkout.graphql.helper import (
    convert_date_time_to_timezone_asia,
    get_alternated_material_related_data,
    get_date_time_now_timezone_asia,
    get_item_no_max_order_line,
    get_name_from_sold_to_partner_address_master,
    get_non_container_materials_from_contract_materials,
    get_sold_to_partner,
    get_summary_details_from_data,
    is_materials_product_group_matching,
    is_other_product_group,
    update_order_lines_item_status_en_and_item_status_th,
    update_order_product_group,
    update_order_status,
)
from scg_checkout.graphql.implementations.iplan import (
    call_i_plan_create_order,
    get_order_remark_order_info,
    get_payment_method_name_from_order,
    get_sale_org_name_from_order,
    get_sold_to_no_name,
    has_special_plant,
    request_api_change_order,
)
from scg_checkout.graphql.implementations.sap import (
    get_error_messages_from_sap_response_for_change_order,
)
from scg_checkout.graphql.resolves.contracts import get_sap_contract_items
from scg_checkout.graphql.resolves.orders import (
    call_sap_es26,
    resolve_bill_to_address,
    resolve_ship_to_address,
)
from scgp_eo_upload.constants import EO_UPLOAD_STATE_ERROR, EO_UPLOAD_STATE_IN_PROGRESS
from scgp_eo_upload.implementations.eo_upload import get_data_path
from scgp_eo_upload.models import EoUploadLog
from scgp_export.error_codes import ScgpExportErrorCode
from scgp_export.graphql.enums import (
    ChangeExportRejectReason,
    IPlanEndPoint,
    ItemCat,
    MaterialGroup,
    SapEnpoint,
    ScgExportOrderLineAction,
    ScgpExportOrder,
    ScgpExportOrderStatus,
    ScgpExportOrderStatusSAP,
    TextID,
)
from scgp_export.graphql.validators import (
    validate_list_have_item_in,
    validate_list_items_equal,
)
from scgp_export.implementations.mapping_data_object import MappingDataToObject
from scgp_export.implementations.sap import get_web_user_name
from scgp_export.sns_helper.sns_connect import setup_client_sns
from scgp_po_upload.graphql.helpers import html_to_pdf
from scgp_po_upload.models import PoUploadFileLog
from scgp_require_attention_items.graphql.helper import (
    update_attention_type_r1,
    update_attention_type_r3,
    update_attention_type_r4,
    update_attention_type_r5,
)
from scgp_require_attention_items.models import RequireAttention, RequireAttentionIPlan
from utils.enums import IPlanInquiryMethodCode

from ..graphql.helper import (
    handle_item_no_flag,
    mapping_new_item_no,
    sync_export_order_from_es26,
)

# flake8: noqa: C901


def get_order_header_updated_fields(order: Order, params: dict):
    if params is None:
        return None
    updatable_fields = [
        "ship_to",
        "bill_to",
        "po_no",
        "request_date",
        "ref_pi_no",
        "usage",
        "unloading_point",
        "place_of_delivery",
        "port_of_discharge",
        "port_of_loading",
        "no_of_containers",
        "uom",
        "gw_uom",
        "etd",
        "eta",
        "dlc_expiry_date",
        "dlc_no",
        "dlc_latest_delivery_date",
        "description",
        "payment_instruction",
        "production_information",
        "remark",
        "internal_comment_to_warehouse",
    ]

    updated_data = {}

    for field in updatable_fields:
        order_data_field = getattr(order, field, None)
        order_update_data_field = params.get(field, None)

        if isinstance(order_data_field, datetime):
            order_update_data_field = datetime.strptime(
                order_update_data_field, "%Y-%m-%d"
            ).strftime("%d/%m/%Y")
        if field == "eta" and order_update_data_field:
            date_obj = datetime.strptime(order_update_data_field, "%Y-%m-%d")
            order_update_data_field = date_obj.date()
            if order_data_field != order_update_data_field:
                order_update_data_fields = date_obj.strftime("%d/%m/%Y")
                updated_data.update({field: order_update_data_fields})
        elif field == "etd" and order_data_field != order_update_data_field:
            etd_datetime = datetime.strptime(order_update_data_field, "%Y-%m-%d")
            order_update_data_field = etd_datetime.strftime("%d/%m/%Y")
            updated_data.update({field: order_update_data_field})

        else:
            if order_data_field != order_update_data_field:
                updated_data.update({field: order_update_data_field})

    return updated_data


def get_order_items_updated_data(params: dict):
    pass


@transaction.atomic
def update_export_order(order_id, params, user, info):
    try:
        manage = info.context.plugins
        order = Order.objects.filter(Q(id=order_id) | Q(so_no=order_id)).first()
        original_order = deepcopy(order)
        order_header_updated_data = get_order_header_updated_fields(
            order, params.get("order_header", None)
        )
        logging.info(
            f"[Export create order] For Order id: {order.id}, FE request: {params}"
            f" by user: {user} "
        )

        # order_items_updated_data = get
        request_date_data = order.request_date
        today = date.today()

        line_ids = list(map(lambda x: x.get("id"), params.get("lines", [])))
        item_no_flags = handle_item_no_flag(order, params)
        item_no_update = [
            item_no for item_no, key in item_no_flags.items() if key == "U"
        ]
        pre_update_items = OrderLines.objects.filter(
            order=order, item_no__in=item_no_update
        ).in_bulk(field_name="id")

        if (
            params.get("order_header")
            and not params.get("order_header").get("etd")
            and params.get("status") == ScgpExportOrderStatus.CONFIRMED.value
        ):
            raise ValidationError(
                {
                    "etd": ValidationError(
                        "ETD is required",
                        code=ScgpExportErrorCode.NOT_FOUND.value,
                    )
                }
            )

        # Validate request date
        if (
            params
            and params.get("order_header")
            and params.get("order_header").get("request_date")
            and params.get("status") == ScgpExportOrderStatus.CONFIRMED.value
        ):
            request_date = params.get("order_header").get("request_date")
            if request_date_data != request_date:
                if order.status in (
                    ScgpExportOrderStatus.DRAFT.value,
                    ScgpExportOrderStatus.PRE_DRAFT.value,
                ) or (
                    order.status
                    not in (
                        ScgpExportOrderStatus.DRAFT.value,
                        ScgpExportOrderStatus.PRE_DRAFT.value,
                    )
                    and request_date != order.request_date
                ):
                    if request_date <= today:
                        raise ValidationError(
                            {
                                "request_date": ValidationError(
                                    "Request date must be further than today",
                                    code=ScgpExportErrorCode.INVALID.value,
                                )
                            }
                        )

        # AGENCY
        if params.get("agency") and order.status in (
            ScgpExportOrderStatus.DRAFT.value,
            ScgpExportOrderStatus.PRE_DRAFT.value,
        ):
            agency = params.get("agency")

            order.order_type = agency.get("order_type", order.order_type)
            order.sales_organization_id = agency.get(
                "sales_organization_id", order.sales_organization_id
            )
            order.distribution_channel_id = agency.get(
                "distribution_channel_id", order.distribution_channel_id
            )
            order.division_id = agency.get("division_id", order.division_id)
            order.sales_office_id = agency.get("sales_office_id", order.sales_office_id)
            order.sales_group_id = agency.get("sales_group_id", order.sales_group_id)

        # Header
        if params.get("order_header"):
            order_header = params.get("order_header")
            validate_when_status_is_partial_delivery(order, None, {}, order_header)
            update_order_header(order, order_header)

        # Update order status
        status = params.get("status")
        if (
            order.status == ScgpExportOrderStatus.PRE_DRAFT.value
            and status == ScgpExportOrderStatus.DRAFT.value
        ):
            order.status = status

        if order.status in (
            ScgpExportOrderStatus.DRAFT.value,
            ScgpExportOrderStatus.PRE_DRAFT.value,
        ) and (
            status == ScgpExportOrderStatus.CONFIRMED.value
            or status == ScgpExportOrderStatus.RECEIVED_ORDER.value
        ):
            if order.status == ScgpExportOrderStatus.DRAFT.value:
                deduct_quantity_cart_item(order_id, user)
                # deduct_remaining_quantity_pi_product(order_id, user)

            if status == ScgpExportOrderStatus.CONFIRMED.value:
                manager = info.context.plugins
                # Removed due to cancelled ticket SEO-1110
                # save_sale_employee_partner_data(order, plugin=manager)

                # Add web_user_name when create order
                order.web_user_name = get_web_user_name(
                    order_type=OrderType.EXPORT, user=user
                )
        if params and params.get("order_header"):
            order.request_delivery_date = params.get("order_header").get("request_date")
        order.updated_at = datetime.now()
        order.save()

        order_lines = OrderLines.objects.filter(order_id=order.id).prefetch_related(
            "order", "iplan"
        )
        old_lines = list(order_lines)
        origin_update_line = mapping_new_item_no(old_lines, params) or old_lines
        if len(order_lines) > 0:
            remove_cart_from_orderline(order_lines)

        # Update order lines
        lines = params.get("lines")
        if lines:
            update_lines = []
            create_lines = []
            for line in lines:
                if line.get("id"):
                    update_lines.append(line)
                else:
                    # Validate request date of order line
                    line_request_date = line.get("request_date")
                    if (
                        params.get("status") == ScgpExportOrderStatus.CONFIRMED.value
                        and line_request_date
                        and line_request_date <= today
                    ):
                        raise ValidationError(
                            {
                                "request_date": ValidationError(
                                    "Request date must be further than today",
                                    code=ScgpExportErrorCode.INVALID.value,
                                )
                            }
                        )
                    create_lines.append(line)

            if len(update_lines):
                update_export_order_lines(order_id, update_lines, user, order)

            if len(create_lines):
                create_export_order_lines(order, create_lines)

        OrderLines.objects.filter(order=order, item_no__isnull=True).delete()

        success = True
        sap_order_messages = []
        sap_item_messages = []
        i_plan_messages = []
        warning_messages = []
        if (
            order.status in (ScgOrderStatus.DRAFT.value, ScgOrderStatus.PRE_DRAFT.value)
            and status == ScgOrderStatus.CONFIRMED.value
        ):
            # """SEO-679: If order is in a special case (all iplant are having value in 7533, 7531, 754F"""
            # if is_order_has_special_plant(order):
            #     OrderLines.objects.filter(order_id=order.pk).update(
            #         confirmed_date=order.etd_date
            #     )
            #     sap_response = request_create_order_sap(order, manager=manage)
            #     sap_order_number = sap_response.get("salesdocument")
            #     sap_success = True
            #     if sap_response.get("data"):
            #         # Get message for order
            #         for data in sap_response.get("data"):
            #             if data.get("type", "").lower() == SapType.ERROR.value.lower():
            #                 sap_success = False
            #             if data.get("id") and data.get("number"):
            #                 sap_order_messages.append(
            #                     {
            #                         "id": data.get("id"),
            #                         "number": data.get("number"),
            #                         "so_no": sap_response.get("salesdocument"),
            #                     }
            #                 )

            #     success = False
            #     if sap_success:
            #         success = True
            #         order.status = ScgOrderStatus.RECEIVED_ORDER.value
            #         order.status_sap = ScgOrderStatusSAP.COMPLETE.value
            #         order.so_no = sap_order_number
            #         order.eo_no = sap_order_number
            # else:
            # follow logic SEO-961 export order singleSource true
            # response = call_i_plan_create_order(
            #     order, manage, user=info.context.user, order_header_updated_data
            # )
            logging.info(
                f"[Export create order] For Order id: {order.id},calling iplan to create order"
            )
            response = call_i_plan_create_order(
                order,
                manage,
                user=info.context.user,
                order_header_updated_data=order_header_updated_data,
            )

            if response.get("success"):
                order.status = response.get("order_status")
                order.so_no = response.get("sap_order_number")
                update_order_lines_item_status_en_and_item_status_th(
                    order,
                    order_lines,
                    IPlanOrderItemStatus.ITEM_CREATED.value,
                    IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
                        IPlanOrderItemStatus.ITEM_CREATED.value
                    ),
                )
            else:
                success = False
            order.status_sap = response.get("sap_order_status")
            sap_order_messages = response.get("sap_order_messages")
            sap_item_messages = response.get("sap_item_messages") or []
            i_plan_messages = response.get("i_plan_messages")
            warning_messages = response.get("warning_messages")
        elif order.status not in (
            ScgpExportOrderStatus.DRAFT.value,
            ScgpExportOrderStatus.PRE_DRAFT.value,
        ):
            # Case update order
            logging.error(
                f"Duplicate order creation request found. An order already exists with the same EO No {order.so_no}"
            )
            raise ValidationError(
                {
                    "create_order": ValidationError(
                        f"Duplicate order creation request found. An order already exists with the same EO No {order.so_no}",
                        code=ScgpExportErrorCode.DUPLICATE_ORDER.value,
                    )
                }
            )

            manager = info.context.plugins
            # """SEO-679: If order is in a special case (all iplant are having value in 7533, 7531, 754F"""
            # if is_order_has_special_plant(order):
            #     OrderLines.objects.filter(order_id=order.pk).update(
            #         confirmed_date=order.etd_date
            #     )
            #     request_change_order_sap(order, manager=manager)
            # else:
            updated_order_lines = list(OrderLines.objects.filter(order=order))
            response = request_api_change_order(
                order,
                manager,
                origin_update_line,
                updated_order_lines,
                sap_update_flag=item_no_flags,
                original_order=original_order,
                updated_data=order_header_updated_data,
                pre_update_lines=pre_update_items,
            )
            if not response.get("success"):
                # Rollback when SAP return fail
                transaction.set_rollback(True)
                success = False

            sap_order_messages = response.get("sap_order_messages")
            sap_item_messages = response.get("sap_item_messages") or []
            i_plan_messages = response.get("i_plan_messages")

        # Rollback when call API fail
        if not success:
            transaction.set_rollback(True)
        else:
            order.save()
            mock_confirmed_date(order)

            # Update attention type
            attention_order_lines = OrderLines.objects.filter(
                order_id=order_id
            ).select_related("iplan", "order")
            update_attention_type_r1(attention_order_lines)
            update_attention_type_r3(attention_order_lines)
            update_attention_type_r4(attention_order_lines)
            OrderLines.objects.bulk_update(attention_order_lines, ["attention_type"])
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
    except ValidationError as validation_error:
        logging.info(
            f"  ValidationError {validation_error} while creating Export order for Order id: {order.id}"
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
            validation_error,
        )
    except Exception as e:
        logging.info(
            f"  Exception {e} while creating Export order for Order id: {order.id}"
            f" by user: {info.context.user}"
        )
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


@transaction.atomic
def update_export_order_line_draft(order_lines):
    order_lines_update = []
    for line in order_lines:
        order_line = OrderLines.objects.get(id=line.get("id"))
        order_line.quantity = line.get("quantity") or order_line.quantity
        order_line.request_date = line.get("request_date") or order_line.request_date
        order_lines_update.append(order_line)
    OrderLines.objects.bulk_update(order_lines_update, ["quantity", "request_date"])
    return order_lines_update


def is_order_has_special_plant(order: Order):
    contract_material_ids = list(
        OrderLines.objects.filter(order_id=order.pk).values_list(
            "contract_material", flat=True
        )
    )

    plants = list(
        ContractMaterial.objects.filter(id__in=contract_material_ids).values_list(
            "plant", flat=True
        )
    )
    """The order is in special case if the plant of all orderline is the same"""
    """and plants have value in 754F, 7531, 7533"""
    return validate_list_items_equal(lst=plants) and validate_list_have_item_in(
        lst=plants, haystack=["754F", "7531", "7533"]
    )


def update_order_header(order, order_header):
    updatable_field = [
        "ship_to",
        "po_no",
        "request_date",
        "usage",
        "unloading_point",
        "place_of_delivery",
        "bill_to",
        "payer",
        "internal_comment_to_warehouse",
        "remark",
        "payment_instruction",
        "port_of_discharge",
        "no_of_containers",
        "etd",
        "eta",
        "dlc_no",
        "dlc_expiry_date",
        "dlc_latest_delivery_date",
        "description",
        "port_of_loading",
        "production_information",
        "uom",
        "gw_uom",
        "ref_pi_no",
        "incoterms_2",
        "end_customer",
    ]

    if order.status in (
        ScgpExportOrderStatus.DRAFT.value,
        ScgpExportOrderStatus.PRE_DRAFT.value,
    ):
        updatable_field = order_header.keys()

    for order_attr_name in updatable_field:
        if order_attr_name in order_header:
            order_attr_value = order_header.get(order_attr_name)
            if getattr(order, order_attr_name) != order_attr_value:
                setattr(order, order_attr_name, order_attr_value)

    return order


def query_invalid_order_lines(order_id):
    """
    filter line have null value
    """
    query = Q(order__id=order_id)

    # Check is null
    null_query = Q()
    null_query.add(Q(material_id__isnull=True), Q.OR)
    null_query.add(Q(quantity__isnull=True), Q.OR)
    null_query.add(Q(quantity_unit__isnull=True), Q.OR)
    null_query.add(Q(weight__isnull=True), Q.OR)
    null_query.add(Q(weight_unit__isnull=True), Q.OR)
    null_query.add(Q(net_price__isnull=True), Q.OR)
    null_query.add(Q(vat_percent__isnull=True), Q.OR)
    # null_query.add(Q(item_cat_eo__isnull=True), Q.OR)
    # null_query.add(Q(plant__isnull=True), Q.OR)
    null_query.add(Q(material_code__isnull=True), Q.OR)
    null_query.add(Q(condition_group1__isnull=True), Q.OR)
    null_query.add(Q(material_group2__isnull=True), Q.OR)
    null_query.add(Q(commission_percent__isnull=True), Q.OR)
    null_query.add(Q(commission_amount__isnull=True), Q.OR)
    null_query.add(Q(commission_unit__isnull=True), Q.OR)
    null_query.add(Q(request_date__isnull=True), Q.OR)
    null_query.add(Q(route__isnull=True), Q.OR)
    null_query.add(Q(delivery_tol_under__isnull=True), Q.OR)
    null_query.add(Q(delivery_tol_over__isnull=True), Q.OR)
    null_query.add(Q(delivery_tol_unlimited__isnull=True), Q.OR)
    null_query.add(Q(roll_diameter__isnull=True), Q.OR)
    null_query.add(Q(roll_core_diameter__isnull=True), Q.OR)
    null_query.add(Q(roll_quantity__isnull=True), Q.OR)
    null_query.add(Q(roll_per_pallet__isnull=True), Q.OR)
    null_query.add(Q(pallet_size__isnull=True), Q.OR)
    null_query.add(Q(pallet_no__isnull=True), Q.OR)
    null_query.add(Q(package_quantity__isnull=True), Q.OR)
    null_query.add(Q(packing_list__isnull=True), Q.OR)
    null_query.add(Q(shipping_point__isnull=True), Q.OR)
    null_query.add(Q(reject_reason__isnull=True), Q.OR)

    # Check is empty string
    empty_query = Q()
    empty_query.add(Q(quantity_unit=""), Q.OR)
    empty_query.add(Q(weight_unit=""), Q.OR)
    empty_query.add(Q(item_cat_eo=""), Q.OR)
    # empty_query.add(Q(plant=""), Q.OR)
    empty_query.add(Q(material_code=""), Q.OR)
    empty_query.add(Q(condition_group1=""), Q.OR)
    empty_query.add(Q(material_group2=""), Q.OR)
    empty_query.add(Q(commission_unit=""), Q.OR)
    empty_query.add(Q(route=""), Q.OR)
    empty_query.add(Q(pallet_size=""), Q.OR)
    empty_query.add(Q(pallet_no=""), Q.OR)
    empty_query.add(Q(packing_list=""), Q.OR)
    empty_query.add(Q(shipping_point=""), Q.OR)
    empty_query.add(Q(reject_reason=""), Q.OR)

    return OrderLines.objects.filter(query & (null_query | empty_query)).all()


@transaction.atomic
def update_export_order_lines(order_id, params, user, order=None):
    try:
        order_line_ids = [order_line_data.get("id") for order_line_data in params]
        order_lines = OrderLines.objects.filter(pk__in=order_line_ids)
        dict_line_objects = {}
        for line in order_lines:
            line_id = str(line.id)
            dict_line_objects[line_id] = line
            order_line_ids.remove(line_id)

        if len(order_line_ids):
            raise ValidationError(
                {
                    "id": ValidationError(
                        f"Order line {order_line_ids[0]} don't exist.",
                        code=ScgpExportErrorCode.NOT_FOUND.value,
                    )
                }
            )

        updatable_fields = [
            "item_no",
            "quantity",
            "quantity_unit",
            "weight_unit",
            "weight",
            "item_cat_eo",
            "plant",
            "ref_pi_no",
            "request_date",
            "reject_reason",
            "route",
            "roll_quantity",
            "roll_diameter",
            "roll_core_diameter",
            "pallet_size",
            "roll_per_pallet",
            "pallet_no",
            "package_quantity",
            "packing_list",
            "shipping_point",
            "delivery_tol_over",
            "delivery_tol_under",
            "delivery_tol_unlimited",
            "net_price",
            "commission_amount",
            "original_request_date",
            "shipping_mark",
        ]

        if order is None:
            order = Order.objects.get(Q(id=order_id) | Q(so_no=order_id))

        update_line_objects = []
        today = date.today()
        for order_line_data in params:
            line_object = dict_line_objects.get(order_line_data.pop("id").lstrip("0"))
            validate_when_status_is_partial_delivery(
                order, line_object, order_line_data
            )
            # Validate request date of order line
            line_request_date = order_line_data.get("request_date")
            if line_request_date:
                if order.status in (
                    ScgpExportOrderStatus.DRAFT.value,
                    ScgpExportOrderStatus.PRE_DRAFT.value,
                ) or (
                    order.status
                    not in (
                        ScgpExportOrderStatus.DRAFT.value,
                        ScgpExportOrderStatus.PRE_DRAFT.value,
                    )
                    and line_request_date != line_object.request_date
                ):
                    if line_request_date <= today:
                        raise ValidationError(
                            {
                                "request_date": ValidationError(
                                    "Request date must be further than today",
                                    code=ScgpExportErrorCode.INVALID.value,
                                )
                            }
                        )

            # If data is changed, add line_object to update_line_objects
            changed_order_line = handle_update_order_line(
                order_line_data, line_object, updatable_fields
            )
            if changed_order_line:
                update_line_objects.append(changed_order_line)

        if len(update_line_objects):
            OrderLines.objects.bulk_update(update_line_objects, updatable_fields)

        order = sync_order_prices(order_id)

        return True, order
    except ValidationError as validation_error:
        transaction.set_rollback(True)
        raise validation_error
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def handle_update_order_line(order_line_data, line_object, updatable_fields):
    is_changed = False
    if not line_object.original_request_date:
        line_object.original_request_date = order_line_data.get("request_date")
    # Check data is changed or not
    for updatable_field in updatable_fields:
        if updatable_field in order_line_data and getattr(
            line_object, updatable_field
        ) != order_line_data.get(updatable_field):
            is_changed = True
            setattr(line_object, updatable_field, order_line_data.get(updatable_field))

    # Re-calc net price and commission for order line
    if order_line_data.get("quantity") and line_object.contract_material:
        order_line_net_price = (
            order_line_data.get("quantity")
            * line_object.contract_material.price_per_unit
        )
        if line_object.net_price != order_line_net_price:
            line_object.net_price = order_line_net_price
            line_object.commission_amount = (
                (order_line_net_price * line_object.commission_percent / 100)
                if line_object.commission_percent
                else None
            )
            is_changed = True

    if is_changed:
        return line_object

    return False


@transaction.atomic
def create_export_order(info, input_data):
    try:

        order_data, order_lines_data = handle_order_data(input_data, info=info)
        contract_materials = []
        for checkout_line in order_lines_data:
            contract_materials.append(checkout_line.get("contract_material"))
        contract_materials = get_non_container_materials_from_contract_materials(
            contract_materials
        )
        if not is_materials_product_group_matching(
            None, contract_materials, order_data.get("type")
        ):
            raise ValidationError(
                {
                    "product_group": ValidationError(
                        "Please select the same product group to create an order",
                        code=ScgpExportErrorCode.PRODUCT_GROUP_ERROR.value,
                    )
                }
            )
        product_group = (
            contract_materials[0].mat_group_1 if contract_materials else None
        )

        order = Order.objects.create(
            product_group=product_group,
            contract=order_data.get("contract"),
            sold_to=order_data.get("sold_to"),
            net_price=order_data.get("net_price"),
            tax_amount=order_data.get("tax_amount"),
            total_price=order_data.get("total_price"),
            doc_currency=order_data.get("doc_currency"),
            status=order_data.get("status"),
            payment_term=order_data.get("payment_term"),
            incoterm=order_data.get("incoterm"),
            shipping_mark=order_data.get("shipping_mark"),
            contact_person=order_data.get("contact_person"),
            sales_employee=order_data.get("sales_employee"),
            author=order_data.get("author"),
            created_by=info.context.user,
            order_type=order_data.get("order_type"),
            sales_organization=order_data.get("sales_organization"),
            distribution_channel=order_data.get("distribution_channel"),
            division=order_data.get("division"),
            sales_office=order_data.get("sales_office"),
            sales_group=order_data.get("sales_group"),
            po_no=order_data.get("po_no"),
            request_date=order_data.get("request_date", None),
            ref_pi_no=order_data.get("ref_pi_no"),
            usage=order_data.get("usage_no"),
            unloading_point=order_data.get("unloading_point"),
            place_of_delivery=order_data.get("place_of_delivery"),
            port_of_discharge=order_data.get("port_of_discharge"),
            port_of_loading=order_data.get("port_of_loading"),
            no_of_containers=order_data.get("no_of_containers"),
            uom=order_data.get("uom"),
            gw_uom=order_data.get("gw_uom"),
            eta=order_data.get("eta", None),
            dlc_expiry_date=order_data.get("dlc_expiry_date"),
            dlc_no=order_data.get("dlc_no"),
            dlc_latest_delivery_date=order_data.get("dlc_latest_delivery_date"),
            description=order_data.get("description"),
            payer=order_data.get("payer"),
            end_customer=order_data.get("end_customer"),
            ship_to=order_data.get("ship_to"),
            bill_to=order_data.get("bill_to"),
            created_at=order_data.get("created_at"),
            updated_at=order_data.get("updated_at"),
            eo_no=order_data.get("eo_no"),
            etd_date=order_data.get("etd_date", None),
            etd=order_data.get("etd", None),
            type=order_data.get("type"),
            web_user_name="",
            currency=order_data.get("currency"),
            remark=order_data.get("remark"),
            production_information=order_data.get("production_information"),
            internal_comment_to_warehouse=order_data.get(
                "internal_comment_to_warehouse"
            ),
            payment_instruction=order_data.get("payment_instruction"),
            incoterms_2=order_data.get("incoterms_2"),
        )

        # save shipTo party and billTo party into order
        contract = order_data.get("contract")
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
        order_lines_i_plan = []
        for order_line_data in order_lines_data:
            i_plan = OrderLineIPlan(
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
            order_lines_i_plan.append(i_plan)
            order_line = OrderLines(
                order=order,
                material=order_line_data.get("material"),
                material_variant=order_line_data.get("material_variant"),
                contract_material=order_line_data.get("contract_material"),
                quantity=order_line_data.get("quantity"),
                quantity_unit=order_line_data.get("quantity_unit"),
                weight=order_line_data.get("weight"),
                weight_unit=order_line_data.get("weight_unit"),
                vat_percent=order_line_data.get("vat_percent"),
                commission_percent=order_line_data.get("commission_percent"),
                commission_amount=order_line_data.get("commission_amount"),
                commission_unit=order_line_data.get("commission_unit"),
                condition_group1=order_line_data.get("condition_group1"),
                material_group2=order_line_data.get("material_group2"),
                cart_item=order_line_data.get("cart_item"),
                item_no=order_line_data.get("item_no"),
                net_price=order_line_data.get("net_price"),
                material_code=order_line_data.get("material_code"),
                item_cat_eo=order_line_data.get("item_cat_eo"),
                # plant=order_line_data.get("plant"),
                ref_pi_no=order_line_data.get("ref_pi_no"),
                request_date=order_line_data.get("request_date"),
                route=order_line_data.get("route"),
                delivery_tol_over=order_line_data.get("delivery_tol_over"),
                delivery_tol_under=order_line_data.get("delivery_tol_under"),
                delivery_tol_unlimited=order_line_data.get("delivery_tol_unlimited"),
                roll_diameter=order_line_data.get("roll_diameter"),
                roll_core_diameter=order_line_data.get("roll_core_diameter"),
                roll_quantity=order_line_data.get("roll_quantity"),
                roll_per_pallet=order_line_data.get("roll_per_pallet"),
                pallet_size=order_line_data.get("pallet_size"),
                pallet_no=order_line_data.get("pallet_no"),
                package_quantity=order_line_data.get("package_quantity"),
                packing_list=order_line_data.get("packing_list"),
                shipping_point=order_line_data.get("shipping_point"),
                shipping_mark=order_line_data.get("shipping_mark"),
                reject_reason=order_line_data.get("reject_reason"),
                inquiry_method=InquiryMethodType.EXPORT.value,
                iplan=i_plan,
                sales_unit=order_line_data.get("material_variant").sales_unit,
                sap_confirm_status=random.choice(
                    SapOrderConfirmationStatus.SAP_ORDER_CONFIRMATION_STATUS_LIST.value
                ),
                ref_doc_it=order_line_data.get("contract_material").item_no
                if order_line_data.get("contract_material")
                else None,
                payment_term_item=order_line_data.get("contract_material").payment_term,
                remark=order_line_data.get("remark", ""),
            )
            order_lines.append(order_line)
        OrderLineIPlan.objects.bulk_create(order_lines_i_plan)
        OrderLines.objects.bulk_create(order_lines)

        # data_input = {
        #     "contract_no": order.contract.code,
        #     "sold_to_code": order.sold_to.sold_to_code,
        #     "sales_org_code": order.sales_organization.code,
        # }
        # credit_limit = resolve_get_credit_limit(info, data_input)
        # if credit_limit.get("credit_block_status", False):
        #     transaction.set_rollback(True)
        #     return None

        return order
    except ValidationError as e:
        raise e
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def handle_order_addition_order_data_from_soldtotextmaster(contract):
    return (
        sap_master_data_models.SoldToTextMaster.objects.filter(
            Q(
                Q(sold_to_code=contract.sold_to.sold_to_code, language="EN")
                | Q(sold_to_code=contract.sold_to.sold_to_code, language="TH")
            )
            & Q(sales_organization_code=contract.sales_organization.code)
            & Q(distribution_channel_code=contract.distribution_channel.code)
            & Q(division_code=contract.division.code)
        )
        .distinct("text_id")
        .in_bulk(field_name="text_id")
    )


def prepare_item_header_remark(order_texts, mapping_code, item_no):
    result = {}
    for order_text in order_texts:
        if (
            order_text.get("ItemNo") == str(item_no).zfill(6)
            and order_text.get("textId") == mapping_code
        ):
            if order_text.get("ItemNo") not in result:
                result[order_text.get("ItemNo")] = {}
            result[order_text.get("ItemNo").lstrip("0")] = join_header_text_lines(
                order_text.get("headerTextList")
            )
    return result


def join_header_text_lines(header_texts):
    rs = ""
    for header_text in header_texts:
        rs += header_text.get("headerText") + "\n"
    return rs[:-1]


def handle_order_data(params, info=None):
    """
    Validate and handle data for order
    return dict order_data and list order_lines_data
    """
    order_header = params.get("order_header")
    lines = sorted(params.get("lines"), key=lambda d: int(d["pi_product"]))

    order_lines_data = []
    contract = Contract.objects.get(id=order_header.get("pi_id"))
    sold_to = contract.sold_to
    sold_to_code = sold_to.sold_to_code
    tax_percent = fn.get_tax_percent(sold_to_code)
    # find unloading point
    unloading_point = ""
    # if not sold_to_code but it should required
    if sold_to_code:
        unloading_point_obj = SoldToUnloadingPointMaster.objects.filter(
            sold_to_code=sold_to_code
        ).last()
        unloading_point = (
            unloading_point_obj and unloading_point_obj.unloading_point or ""
        )

    contract_material_ids = []
    material_codes = []
    sales_organization_code = (
        contract.sales_organization.code if contract.sales_organization else None
    )
    distribution_channel_code = (
        contract.distribution_channel.code if contract.distribution_channel else None
    )
    for line in lines:
        contract_material_ids.append(line.get("pi_product"))

    # Get all contract material of order
    dict_contract_material = {}
    material_ids = []
    qs_contract_materials = ContractMaterial.objects.select_related("material").filter(
        id__in=contract_material_ids
    )
    for contract_material in qs_contract_materials:
        dict_contract_material[str(contract_material.id)] = contract_material
        material_ids.append(contract_material.material.id)
        material_codes.append(contract_material.material.material_code)

    # Get all material variant of order
    dict_material_variants = {}
    qs_material_materials = (
        MaterialVariantMaster.objects.filter(material_id__in=material_ids)
        .order_by("material_id", "id")
        .distinct("material_id")
    )
    for material_variant in qs_material_materials:
        dict_material_variants[str(material_variant.material_id)] = material_variant

    order_net_price = 0
    order_currency = None
    item_no = 10

    channel_master = sap_master_data_models.SoldToChannelMaster.objects.filter(
        sold_to_code=sold_to_code,
        sales_organization_code=sales_organization_code,
        distribution_channel_code=distribution_channel_code,
    ).first()

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

    material_conversion_values = (
        sap_master_data_models.Conversion2Master.objects.filter(
            material_code__in=material_codes, to_unit="ROL"
        )
        .order_by("material_code", "-id")
        .distinct("material_code")
        .in_bulk(field_name="material_code")
    )

    response = get_sap_contract_items(
        info.context.plugins.call_api_sap_client, contract_no=contract.code
    )
    response_data = response.get("data", [{}])[0]
    order_text_list = response_data.get("orderText", [])

    for index, line in enumerate(lines):
        contract_material = dict_contract_material.get(str(line.get("pi_product")))
        if not contract_material:
            raise ValidationError(
                {
                    "contract_material": ValidationError(
                        f"Contract material {line.get('pi_product')} don't exist.",
                        code=ScgpExportErrorCode.NOT_FOUND.value,
                    )
                }
            )

        material = contract_material.material
        material_code = material.material_code

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
                        f"Contract material {line.get('pi_product')} don't have material variant.",
                        code=ScgpExportErrorCode.NOT_FOUND.value,
                    )
                }
            )

        quantity = line.get("quantity", 0)

        order_line_currency = contract_material.currency
        if not order_currency:
            order_currency = order_line_currency
        cart_item_id = line.get("cart_item_id")
        cart_item = CartLines.objects.filter(id=cart_item_id).first()
        weight_conversion_value = getattr(
            material_conversion_values.get(contract_material.material_code),
            "calculation",
            0,
        )
        order_line_net_price = (
            (weight_conversion_value / 1000)
            * contract_material.price_per_unit
            * quantity
        )
        order_net_price += order_line_net_price
        item_no_line = item_no + (index * item_no)
        shipping_mark = next(
            (
                x.get("headerTextList")
                for x in order_text_list
                if x.get("itemNo") == str(item_no_line).zfill(6)
                and x.get("textId") == "Z004"
            ),
            [],
        )
        shipping_mark = "\n".join([x.get("headerText") for x in shipping_mark])
        order_lines_data.append(
            {
                "material": material,
                "material_variant": material_variant,
                "material_code": contract_material.material_code,
                "contract_material": contract_material,
                "quantity": quantity,
                "quantity_unit": contract_material.quantity_unit,
                "weight": (weight_conversion_value / 1000) * quantity
                if contract_material.material.material_group != "PK00"
                else 0,
                "weight_unit": contract_material.weight_unit,
                "net_price": order_line_net_price,
                "vat_percent": tax_percent * 100,
                "condition_group1": contract_material.condition_group1,
                "material_group2": f"{material_sale_master.material_group1} - {material_sale_master.material_group1_desc}"
                if material_sale_master
                else "",
                "cart_item": cart_item,
                "item_no": item_no_line,
                "item_cat_eo": "ZKC0"
                if material.material_group == MaterialGroup.PK00.value
                else "",
                # "plant": contract_material.plant or "",
                "ref_pi_no": "",
                "route": "",
                "delivery_tol_over": channel_master.over_delivery_tol
                if channel_master
                else None,
                "delivery_tol_under": channel_master.under_delivery_tol
                if channel_master
                else None,
                "delivery_tol_unlimited": False,
                "roll_diameter": material_classification_master.diameter
                if material_classification_master
                else "",
                "roll_core_diameter": material_classification_master.core_size
                if material_classification_master
                else "",
                "roll_quantity": 150,
                "roll_per_pallet": 300,
                "pallet_size": "NP",
                "pallet_no": "1-150",
                "package_quantity": 168,
                "packing_list": "1 ROLL x 151 PACKAGES DIMENSION (WxLxH):40'x40'x34'",
                "shipping_point": "",
                "reject_reason": "no",
                "commission_percent": contract_material.commission,
                "commission_amount": contract_material.commission_amount,
                "commission_unit": contract_material.com_unit,
                "shipping_mark": shipping_mark,
            }
        )

    now = datetime.now()
    tax_amount = order_net_price * tax_percent
    order_data = {
        "contract": contract,
        "sold_to": sold_to,
        "net_price": order_net_price,
        "tax_amount": tax_amount,
        "total_price": order_net_price + tax_amount,
        "doc_currency": contract.currency or "",
        "status": OrderStatus.PRE_DRAFT,
        "payment_term": contract.payment_term_key + " - " + contract.payment_term,
        "incoterm": contract.incoterm,
        "shipping_mark": contract.shipping_mark,
        # Get data from API ES14
        "contact_person": contract.contact_person or "",  # Get data from API ES14
        "sales_employee": contract.sales_employee or "",  # Get data from API ES14
        "author": contract.author or "",  # Get data from API ES14
        "ship_to": contract.ship_to,
        "bill_to": contract.bill_to,
        "order_type": "ZOR",
        "sales_organization": contract.sales_organization,
        "distribution_channel": contract.distribution_channel,
        "division": contract.division,
        "sales_office": contract.sales_office,
        "sales_group": contract.sales_group,
        "po_date": None,
        "po_no": contract.po_no,
        "request_date": contract.etd - timedelta(days=10) if contract.etd else None,
        "ref_pi_no": "",
        "usage": contract.usage or "",
        "usage_no": contract.usage_no or "",
        "unloading_point": contract.unloading_point or "",
        "place_of_delivery": contract.incoterms_2 or "",
        "port_of_discharge": contract.port_of_discharge or "",
        "port_of_loading": contract.port_of_loading or "",
        "no_of_containers": contract.no_of_containers or None,
        "uom": contract.uom or "",
        "gw_uom": contract.gw_uom or "",
        "payment_instruction": contract.payment_instruction or "",
        "eta": contract.eta or None,
        "dlc_expiry_date": None,
        "dlc_no": None,
        "dlc_latest_delivery_date": None,
        "description": contract.project_name,
        "payer": contract.payer or "",
        "end_customer": contract.end_customer or "",
        "created_at": now,
        "updated_at": now,
        "eo_no": f"EO00000{random.randint(100, 999)}",
        "etd": contract.etd or None,
        "etd_date": contract.etd or None,
        "type": OrderType.EXPORT.value,
        "remark": contract.remark or "",
        "production_information": contract.production_information or "",
        "internal_comment_to_warehouse": contract.internal_comments_to_warehouse or "",
        "incoterms_2": contract.incoterms_2,
    }
    return order_data, order_lines_data


@transaction.atomic
def delete_export_order_lines(ids, delete_all, order_id, user):
    try:
        order = Order.objects.get(id=order_id)
        weight = 0
        material_codes = []
        if delete_all:
            validate_order(order_id)
            if not order_id:
                raise Exception("order_id is required when delete all")

            order_lines = OrderLines.objects.filter(order_id=order_id)
            if order.status not in (
                ScgpExportOrderStatus.DRAFT.value,
                ScgpExportOrderStatus.PRE_DRAFT.value,
            ):
                for order_line in order_lines:
                    update_remaining_quantity_pi_product_for_completed_order(
                        order_line.contract_material,
                        order_line.quantity,
                        ScgExportOrderLineAction.DELETE.value,
                    )
            export_order_line_ids = order_lines.values_list("id")
            require_attention = RequireAttention.objects.filter(
                items__order_line_id__in=export_order_line_ids, items__type="export"
            )
            require_attention_iplan = RequireAttentionIPlan.objects.filter(
                items__order_line_id__in=export_order_line_ids, items__type="export"
            )
            require_attention.delete()
            require_attention_iplan.delete()
            order_lines.delete()
            update_order_product_group(order_id, None)

        else:
            lines = OrderLines.objects.filter(id__in=ids)
            if lines.count() != len(ids):
                raise Exception("you dont have permission to delete other's order line")

            if not lines.count():
                return True

            if order.status not in (
                ScgpExportOrderStatus.DRAFT.value,
                ScgpExportOrderStatus.PRE_DRAFT.value,
            ):
                for line in lines:
                    material_code = line.material.material_code
                    material_codes.append(material_code)

                conversion_objects = (
                    sap_master_data_models.Conversion2Master.objects.filter(
                        material_code__in=material_codes,
                        to_unit="ROL",
                    )
                    .order_by("material_code", "-id")
                    .distinct("material_code")
                    .in_bulk(field_name="material_code")
                )

                for line in lines:
                    material_code = line.material.material_code
                    conversion_object = conversion_objects.get(str(material_code), None)
                    if conversion_object:
                        calculation = conversion_object.calculation
                        weight = float(calculation) / 1000

                    update_remaining_quantity_pi_product_for_completed_order(
                        line.contract_material,
                        weight,
                        line.quantity,
                        ScgExportOrderLineAction.DELETE.value,
                    )

            export_order_line_ids = lines.values_list("id")
            require_attention = RequireAttention.objects.filter(
                items__order_line_id__in=export_order_line_ids, items__type="export"
            )
            require_attention_iplan = RequireAttentionIPlan.objects.filter(
                items__order_line_id__in=export_order_line_ids, items__type="export"
            )
            require_attention.delete()
            require_attention_iplan.delete()
            lines.delete()

            order_lines = OrderLines.objects.filter(order_id=order_id).order_by("pk")
            item_no = 10
            order_lines_update = []
            for order_line in order_lines:
                order_line.item_no = item_no
                order_lines_update.append(order_line)
                item_no += 10
            order_lines.bulk_update(order_lines_update, ["item_no"])
            if not order_lines:
                update_order_product_group(order_id, None)

        sync_order_prices(order_id)

        return True
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def validate_order(order_id):
    order = Order.objects.filter(Q(id=order_id) | Q(so_no=order_id)).first()
    if not order:
        raise Exception(f"Order with id {order_id} not found!")

    return order


# update total_price, total_price_inc_tax, tax_amount when order lines change
def sync_order_prices(order_id):
    order = Order.objects.filter(Q(id=order_id) | Q(so_no=order_id)).first()
    if order:
        line_total_prices = OrderLines.objects.filter(order_id=order.id).values_list(
            "net_price", flat=True
        )
        total_price = sum(line_total_prices)
        tax_percent = fn.get_tax_percent(order.sold_to.sold_to_code)
        tax_amount = float(total_price) * tax_percent
        order.net_price = float(total_price)
        order.tax_amount = tax_amount
        order.total_price = float(total_price) + tax_amount
        order.updated_at = datetime.now
        order.save()

    return order


@transaction.atomic
def add_products_to_export_order(order_id, products, info):
    try:
        order = validate_order(order_id)
        pi_product_ids = [product.get("pi_product", "") for product in products]
        contract = order.contract
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
        contract_materials = ContractMaterial.objects.filter(id__in=pi_product_ids)

        for pi_product in contract_materials:
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

        max_item_no = get_item_no_max_order_line(order_id)
        max_item_no = max_item_no or 0
        item_no = int(max_item_no) + 10
        weight = 0
        product_group = order.product_group
        contract_materials = get_non_container_materials_from_contract_materials(
            contract_materials
        )
        if not is_materials_product_group_matching(
            product_group, contract_materials, order.type
        ):
            raise ValidationError(
                {
                    "product_group": ValidationError(
                        "Please select the same product group to create an order",
                        code=ScgpExportErrorCode.PRODUCT_GROUP_ERROR.value,
                    )
                }
            )
        if not max_item_no and contract_materials:
            product_group = contract_materials[0].mat_group_1
            update_order_product_group(order_id, product_group)
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
                            f"Contract material {line.get('pi_product')} don't have material variant.",
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
            i_plan = OrderLineIPlan.objects.create(
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
            response = get_sap_contract_items(
                info.context.plugins.call_api_sap_client, contract_no=contract.code
            )
            order_text_list = response.get("data", [{}])[0].get("orderText", [])
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
                net_price=net_price * quantity,
                vat_percent=tax_percent * 100,
                commission_percent=pi_product_object.commission,
                commission_amount=pi_product_object.commission_amount,
                commission_unit=pi_product_object.com_unit,
                item_no=item_no,
                item_cat_eo=ItemCat.ZKC0.value
                if pi_product_object.material.material_group == MaterialGroup.PK00.value
                else "",
                # plant=pi_product_object.plant or "",
                # ref_pi_no=pi_product_object.item_no or "",
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
                shipping_mark=prepare_item_header_remark(
                    order_text_list, TextID.ITEM_SHIPPING_MARK, item_no
                ).get(item_no),
                reject_reason="no",
                inquiry_method=InquiryMethodType.EXPORT.value,
                iplan=i_plan,
                material_group2=f"{material_sale_master.material_group1} - {material_sale_master.material_group1_desc}"
                if material_sale_master
                else "",
                condition_group1=pi_product_object.condition_group1,
            )
            bulk_create_lines.append(line)
            item_no += 10

        if len(bulk_create_lines):
            OrderLines.objects.bulk_create(bulk_create_lines)

        invalid_quantity_line_ids = validate_lines_quantity(order.id, pi_product_ids)
        if invalid_quantity_line_ids:
            raise ValueError(
                f"Total weight of pi products {', '.join(str(line_id) for line_id in invalid_quantity_line_ids)}"
                f" are greater than total remaining "
            )

        return sync_order_prices(order_id)
    except ValidationError as e:
        transaction.set_rollback(True)
        raise e
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def validate_lines_quantity(order_id, pi_product_ids):
    lines = OrderLines.objects.filter(order_id=order_id)
    if pi_product_ids:
        lines = lines.filter(contract_material_id__in=pi_product_ids)
    total_weight_field = DecimalField(max_digits=10, decimal_places=3)
    pi_products = (
        lines.values("contract_material")
        .order_by("contract_material")
        .annotate(
            sum_quantity=Case(
                When(total_weight__isnull=False, then=Sum(F("weight") * F("quantity"))),
                default=Value(0.0),
                output_field=total_weight_field,
            )
        )
        .filter(sum_quantity__gt=F("contract_material__remaining_quantity_ex"))
    )
    pi_product_ids = [pi_product.get("contract_material") for pi_product in pi_products]
    if len(pi_product_ids):
        invalid_quantity_line_ids = OrderLines.objects.filter(
            order_id=order_id,
            contract_material_id__in=pi_product_ids,
        ).values_list("id", flat=True)
        return invalid_quantity_line_ids
    return []


@transaction.atomic
def update_all_export_order_lines(order_id, input_data, user):
    """
    Update all order line (Customer click Apply all)
    """
    try:
        order = Order.objects.get(id=order_id)

        order_lines = OrderLines.objects.filter(order=order)

        if not len(order_lines):
            raise ValidationError(
                {
                    "id": ValidationError(
                        f"Order {order_id} don't have order line.",
                        code=ScgpExportErrorCode.NOT_FOUND.value,
                    )
                }
            )

        updatable_fields = ["request_date"]

        update_line_objects = []
        for order_line in order_lines:
            validate_when_status_is_partial_delivery(order, order_line, input_data)

            for updatable_field in updatable_fields:
                update_value = input_data.get(updatable_field)
                setattr(order_line, updatable_field, update_value)
            update_line_objects.append(order_line)

        OrderLines.objects.bulk_update(update_line_objects, updatable_fields)

        sync_order_prices(order_id)
        return True, order
    except ValidationError as validation_error:
        transaction.set_rollback(True)
        raise validation_error
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def deduct_quantity_cart_item(order_id, user):
    export_order_lines = OrderLines.objects.filter(order_id=order_id)
    cart_ids = []
    for order_line in export_order_lines:
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
        Cart.objects.filter(id__in=cart_ids).annotate(
            total_item=Count("cartlines")
        ).filter(total_item=0).delete()


def deduct_remaining_quantity_pi_product_for_completed_order(
    pi_product, remaining_quantity, new_quantity, old_quantity
):
    new_remaining_quantity = (
        float(remaining_quantity) + float(old_quantity) - float(new_quantity)
    )
    if new_remaining_quantity < 0:
        raise ValueError("Remaining quantity is smaller than line quantity")

    pi_product.remaining_quantity = new_remaining_quantity

    return pi_product


def update_remaining_quantity_pi_product_for_completed_order(
    pi_product, weight, quantity, action
):
    new_remaining_quantity = None
    if action == ScgExportOrderLineAction.UPDATE.value:
        if weight:
            new_remaining_quantity = float(pi_product.remaining_quantity) - (
                float(quantity) * float(weight)
            )
        else:
            new_remaining_quantity = float(pi_product.remaining_quantity) - float(
                quantity
            )

    if action == ScgExportOrderLineAction.DELETE.value:
        new_remaining_quantity = float(pi_product.remaining_quantity) + (
            float(quantity) * float(weight)
        )
    pi_product.remaining_quantity = new_remaining_quantity
    pi_product.save()

    return True


def create_export_order_lines(order, order_lines_data):
    """
    Create order line from popup in footer of order
    """
    exist_lines = OrderLines.objects.filter(
        contract_material_id__in=[line.get("pi_product") for line in order_lines_data],
        order=order,
    )

    if len(exist_lines):
        raise Exception(
            "Unable to add new order item. The product already exists in this order!"
        )

    order_lines = []
    bulk_update_pi_products = []

    max_item_no = get_item_no_max_order_line(order.id)
    max_item_no = max_item_no or 0
    item_no = int(max_item_no) + 10

    for order_line_data in order_lines_data:
        contract_material = ContractMaterial.objects.get(
            id=order_line_data.get("pi_product")
        )
        quantity = order_line_data.get("quantity", 0)
        if quantity <= 0:
            raise ValidationError(
                {
                    "quantity": ValidationError(
                        "The quantity must be greater than 0",
                        code=ScgpExportErrorCode.INVALID.value,
                    )
                }
            )

        order_line_net_price = quantity * contract_material.price_per_unit
        order_line_currency = contract_material.currency
        order_line = OrderLines(
            order=order,
            contract_material=contract_material,
            material=contract_material.material,
            quantity=order_line_data.get("quantity"),
            quantity_unit=order_line_data.get("quantity_unit"),
            weight=contract_material.weight,
            weight_unit=order_line_data.get("weight_unit")
            if order_line_data.get("weight_unit")
            else contract_material.weight_unit,
            vat_percent=ScgpExportOrder.TAX.value * 100,
            commission_percent=ScgpExportOrder.COMMISSION.value * 100,
            commission_amount=order_line_net_price * ScgpExportOrder.COMMISSION.value,
            commission_unit=order_line_currency,
            condition_group1="C2 1: Container 40'",
            material_group2="K01 Kraft roll",
            cart_item=None,
            item_no=order_line_data.get("item_no")
            if order_line_data.get("item_no")
            else item_no,
            net_price=order_line_net_price,
            material_code=contract_material.material.material_code,
            item_cat_eo=order_line_data.get("item_cat_eo")
            if order_line_data.get("item_cat_eo")
            else "",
            # plant=order_line_data.get("plant")
            # if order_line_data.get("plant")
            # else "4312",
            ref_pi_no=order_line_data.get("ref_pi_no")
            if order_line_data.get("ref_pi_no")
            else "510579363",
            request_date=order_line_data.get("request_date")
            if order_line_data.get("request_date")
            else datetime.today() + timedelta(days=14),
            route=order_line_data.get("route")
            if order_line_data.get("route")
            else "VN0005 - นครศรีธรรมราช",
            delivery_tol_over=order_line_data.get("delivery_tol_over")
            if order_line_data.get("delivery_tol_over")
            else 10,
            delivery_tol_under=order_line_data.get("delivery_tol_under")
            if order_line_data.get("delivery_tol_under")
            else 15,
            delivery_tol_unlimited=order_line_data.get("delivery_tol_unlimited")
            if order_line_data.get("delivery_tol_unlimited")
            else False,
            roll_diameter=order_line_data.get("roll_diameter")
            if order_line_data.get("roll_diameter")
            else 42,
            roll_core_diameter=order_line_data.get("roll_core_diameter")
            if order_line_data.get("roll_core_diameter")
            else 3,
            roll_quantity=order_line_data.get("roll_quantity")
            if order_line_data.get("roll_quantity")
            else 150,
            roll_per_pallet=order_line_data.get("roll_per_pallet")
            if order_line_data.get("roll_per_pallet")
            else 300,
            pallet_size=order_line_data.get("pallet_size")
            if order_line_data.get("pallet_size")
            else "NP",
            pallet_no=order_line_data.get("pallet_no")
            if order_line_data.get("pallet_no")
            else "1-150",
            package_quantity=order_line_data.get("package_quantity")
            if order_line_data.get("package_quantity")
            else 168,
            packing_list=order_line_data.get("packing_list")
            if order_line_data.get("packing_list")
            else "1 ROLL x 151 PACKAGES DIMENSION (WxLxH):40'x40'x34'",
            shipping_point=order_line_data.get("shipping_point")
            if order_line_data.get("shipping_point")
            else "5604 - Lorem ipsum dolor adipiscing",
            remark=order_line_data.get("remark")
            if order_line_data.get("remark")
            else "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Ut a dui eu mi porta ornare.",
            reject_reason=order_line_data.get("reject_reason")
            if order_line_data.get("reject_reason")
            else "no",
        )
        order_lines.append(order_line)
        item_no += 10

        # Deduct remain quantity when create new order item
        if order.status not in (
            ScgpExportOrderStatus.DRAFT.value,
            ScgpExportOrderStatus.PRE_DRAFT.value,
        ):
            remaining_quantity = contract_material.remaining_quantity - quantity
            if remaining_quantity < 0:
                raise ValueError(
                    f"Remaining quantity of product {contract_material.id} is smaller than order item quantity"
                )
            contract_material.remaining_quantity = remaining_quantity
            bulk_update_pi_products.append(contract_material)

    if len(order_lines):
        OrderLines.objects.bulk_create(order_lines)

    if len(bulk_update_pi_products):
        ContractMaterial.objects.bulk_update(
            bulk_update_pi_products, ["remaining_quantity"]
        )
    return order_lines


@transaction.atomic
def delete_all_export_order_drafts():
    try:
        order_ids = Order.objects.filter(status="draft").values_list("id")
        order_line_ids = OrderLines.objects.filter(order_id__in=order_ids).values_list(
            "id"
        )

        RequireAttention.objects.filter(
            items__order_line_id__in=order_line_ids, items__type="export"
        ).delete()
        RequireAttentionIPlan.objects.filter(
            items__order_line_id__in=order_line_ids, items__type="export"
        ).delete()

        OrderLines.objects.filter(pk__in=order_line_ids).delete()

        return Order.objects.filter(pk__in=order_ids).delete()
    except Exception as ex:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(ex)


@transaction.atomic
def sync_create_order_to_db(data, user):
    # XXX: FROM EO-UPLOAD
    log_key = "%s|%s|%s" % (
        get_data_path(data, "initial.contract"),
        get_data_path(data, "header.poNo"),
        get_data_path(data, "initial.lotNo"),
    )
    logging.info(f"Start sync_create_order_to_db {log_key}")
    old_log = EoUploadLog.objects.filter(log_key=log_key).last()
    if old_log:
        print("Old log found, skip?")
        # TODO
    try:
        mappingDataToObject = MappingDataToObject()
        initial_parts = mappingDataToObject.map_inital_part(
            data.get("initial"), header=data.get("header")
        )
        header_parts = mappingDataToObject.map_header_part(data.get("header"))

        order_object_dict = {**initial_parts, **header_parts}
        if (
            initial_parts.get("createAndChangeType").lower() == "change"
            or initial_parts.get("createAndChangeType").lower() == "split"
        ):
            find_order_object_db = Order.objects.filter(
                eo_no=order_object_dict.get("eo_no")
            ).last()

            if find_order_object_db:
                order_object_dict["id"] = find_order_object_db.id
        else:
            order_object_dict["web_user_name"] = get_web_user_name(
                order_type=OrderType.EO, user=user
            )

        create_and_change_type = order_object_dict.pop("createAndChangeType") or "new"
        order_object = Order(**order_object_dict)
        order_object.save()
        logging.info(f"  sync_create_order_to_db.created_order {log_key}")

        item_parts_create = mappingDataToObject.map_item_part(
            data.get("items"), order_object.id, create_and_change_type
        )
        if not item_parts_create:
            raise Exception("No item found")

        if len(item_parts_create):

            for item in item_parts_create:
                item.order_id = order_object.id
            OrderLines.objects.bulk_create(item_parts_create)
            order_object.save()
        sync_order_prices(order_object.id)
        dedup_key = "%s|%s" % (order_object.id, create_and_change_type)
        message_data = {
            "order_id": str(order_object.id),
            "order_type": str(create_and_change_type),
        }
        vals = {
            "log_key": log_key,
            "message": json.dumps(message_data),
            "message_attributes": {
                "order_id": {"DataType": "Number", "StringValue": str(order_object.id)},
                "order_type": {
                    "DataType": "String",
                    "StringValue": str(create_and_change_type),
                },
            },
            "message_group_id": str(order_object.id),
            "message_deduplication_id": dedup_key,
            "payload": data,
            "orderid": order_object.id,
            "order_type": create_and_change_type,
            "state": EO_UPLOAD_STATE_IN_PROGRESS,
        }
        EoUploadLog(**vals).save()
        logging.info(f"  sync_create_order_to_db.created_log_in_progress {log_key}")
        # TODO: use plugin settings instead of conf
        setup_client_sns(
            region_name=settings.SNS_EO_DATA_REGION_NAME,
            access_key=settings.SNS_EO_DATA_ACCESS_KEY,
            secret_key=settings.SNS_EO_DATA_SECRET_KEY,
            topic_arn=settings.SNS_EO_DATA_TOPIC_ARN,
            message=json.dumps(message_data),
            subject="eo_data",
            message_attribute={
                "order_id": {"DataType": "Number", "StringValue": str(order_object.id)},
                "order_type": {
                    "DataType": "String",
                    "StringValue": str(create_and_change_type),
                },
            },
            message_group_id="eo_upload",
            message_deduplication_id="eo_upload",
        )
        logging.info(f"  sync_create_order_to_db.send_sns_done {log_key}")
        return order_object

    except Exception as e:
        err_msg = str(e)
        logging.error(
            f"Error sync_create_order_to_db {log_key}: {err_msg} | {traceback.format_exc()}"
        )
        vals = {
            "log_key": log_key,
            "payload": data,
            "state": EO_UPLOAD_STATE_ERROR,
            "error_message": err_msg,
        }
        # TODO: improve this
        # TODO: write without try catch
        try:
            # check old log
            old_log = EoUploadLog.objects.filter(log_key=log_key).last()
            new_log = EoUploadLog(**vals)
            if old_log:
                new_log["id"] = old_log.id
            new_log.save()
        except Exception as e_log:
            err_msg_log = str(e_log)
            logging.info(
                f"Error sync_create_order_to_db when save eo log {log_key}: {err_msg} | {err_msg_log}"
            )


@transaction.atomic
def duplicate_order(so_no, current_user):
    manager = get_plugins_manager()
    sap_fn = manager.call_api_sap_client
    logging.info(f"[Duplicate Order] Order lines product group not matching in {so_no}")
    response = call_sap_es26(so_no=so_no, sap_fn=sap_fn)
    sync_export_order_from_es26(response)
    old_order = Order.objects.get(so_no=so_no)
    old_order_lines = list(old_order.orderlines_set.all())
    old_order_lines.sort(key=lambda line: int(line.item_no))
    contract_material_list = []
    for old_order_line in old_order_lines:
        contract_material_list.append(old_order_line.contract_material)
    if not is_materials_product_group_matching(
        None, contract_material_list, old_order.type
    ):
        logging.error(
            f"[Duplicate Order] Order lines of {old_order.type} order {so_no} product group not matching"
        )
        raise ValidationError(
            {
                "product_group": ValidationError(
                    "Please select an order with line items in the same product group to create a new order.",
                    code=ScgpExportErrorCode.PRODUCT_GROUP_ERROR.value,
                )
            }
        )

    new_order = deepcopy(old_order)
    new_order.item_no_latest = str(len(old_order_lines) * 10)
    new_order.pk = None
    new_order.eo_no = None
    new_order.so_no = None
    new_order.created_by = current_user
    new_order.status = ScgOrderStatus.DRAFT.value
    new_order.eo_upload_log_id = None
    new_order.status_sap = ScgpExportOrderStatusSAP.BEING_PROCESS.value
    new_order.item_no_latest = None
    new_order.save()

    order_lines = []
    item_no = 0
    for old_order_line in old_order_lines:
        item_no += 10
        iplan = sap_migration.models.OrderLineIPlan.objects.create()
        new_order_line = deepcopy(old_order_line)
        new_order_line.pk = None
        new_order_line.order = new_order
        new_order_line.iplan_id = iplan.id
        new_order_line.plant = (
            old_order_line.plant
            if is_other_product_group(old_order_line.prc_group_1)
            else ""
        )
        new_order_line.shipping_point = ""
        new_order_line.route = ""
        new_order_line.item_no = str(item_no)
        new_order_line.delivery = None
        new_order_line.actual_gi_date = None
        new_order_line.gi_status = None
        new_order_line.item_status_en = None
        new_order_line.item_status_th = None
        new_order_line.reject_reason = None
        new_order_line.dtp = None
        new_order_line.dtr = None
        new_order_line.remark = None
        new_order_line.original_request_date = None
        new_order_line.attention_type = None
        new_order_line.request_date_change_reason = None
        new_order_line.class_mark = None
        if new_order.type == OrderType.EXPORT.value:
            new_order_line.inquiry_method = InquiryMethodType.EXPORT.value
            new_order_line.roll_quantity = (
                old_order_line.roll_quantity if old_order_line.roll_quantity else 150
            )
        elif new_order.type == OrderType.DOMESTIC.value:
            new_order_line.inquiry_method = InquiryMethodType.DOMESTIC.value
        else:
            new_order_line.inquiry_method = InquiryMethodType.CUSTOMER.value
        order_lines.append(new_order_line)
    OrderLines.objects.bulk_create(order_lines)

    return new_order


@transaction.atomic
def cancel_export_order(order_id):
    try:
        order = Order.objects.get(id=order_id)
        order.status = ScgpExportOrderStatus.CANCELLED.value
        order.save()
        return order
    except Exception:
        transaction.set_rollback(True)


@transaction.atomic
def cancel_delete_export_order(input_data, info):
    try:
        plugins = info.context.plugins
        so_no = input_data.get("so_no")
        list_item_no = input_data.get("item_nos")
        status = input_data.get("reason")["reason_for_reject"]
        logging.info(
            f" [Export: Cancel/Delete] Order {so_no}, FE request: {input_data},"
            f" by user: {info.context.user}"
        )
        order_lines_object = OrderLines.objects.filter(
            item_no__in=list_item_no, order__so_no=so_no
        )
        order = Order.objects.filter(so_no=so_no).first()

        container_special_plant_items = []
        normal_items = []
        i_plan_messages = []
        es_21_sap_order_messages = []
        es_21_sap_item_messages = []
        sap_order_messages = []
        sap_item_messages = []
        items_success_to_call_es_21 = []
        es_21_sap_response_success = True

        for line in order_lines_object:
            if line.item_cat_eo != ItemCat.ZKC0.value and not has_special_plant(line):
                normal_items.append(line)
            else:
                container_special_plant_items.append(line)

        if normal_items:
            logging.info(f"[Export: Cancel/Delete] for Order {so_no} calling... iplan")
            response_call_i_plan_delete = _call_i_plan_delete_items(
                plugins, normal_items, so_no, order=order
            )
            logging.info(f"[Export: Cancel/Delete] for Order {so_no} called iplan")
            for response in response_call_i_plan_delete[0].get("DDQResponseLine"):
                if response.get("returnStatus").lower() == "failure":
                    i_plan_messages.append(
                        _get_iplan_atp_ctp_error_message(response, so_no)
                    )
                else:
                    items_success_to_call_es_21 = [line for line in normal_items]
        logging.info(
            f" [Export: Cancel/Delete] order {so_no} i_plan_error_messages: {i_plan_messages}"
        )
        container_special_plant_items += items_success_to_call_es_21
        if container_special_plant_items:
            logging.info(f" [Export: Cancel/Delete] for order {so_no} calling... ES21")
            response_call_es21_delete = _call_es_21_delete_items(
                plugins, container_special_plant_items, order, so_no, status
            )
            logging.info(f" [Export: Cancel/Delete] for order {so_no} called ES21")
            (
                es_21_sap_order_messages,
                es_21_sap_item_messages,
                is_being_process,
                es_21_sap_response_success,
            ) = get_error_messages_from_sap_response_for_change_order(
                response_call_es21_delete
            )

            if es_21_sap_order_messages and is_being_process:
                sap_order_message_being_process = es_21_sap_order_messages
                logging.info(
                    f"[Export: Cancel/Delete] sap_order_error_message: {sap_order_message_being_process},"
                    f"order {so_no} is_order_being_processed by other user : {is_being_process}"
                )
                update_attention_type_r5(container_special_plant_items)
                return (
                    i_plan_messages,
                    sap_order_message_being_process,
                    sap_item_messages,
                )

        if not es_21_sap_response_success:
            update_attention_type_r5(container_special_plant_items)

        if es_21_sap_response_success:
            if status == ChangeExportRejectReason.CANCEL_93.value:
                _update_reject_reason_for_items(container_special_plant_items)
                status_en, status_thai = update_order_status(order.id)
                order.status = status_en
                order.status_thai = status_thai
                order.update_by = info.context.user
                logging.info(
                    f"[Export: Cancel/Delete] Item {list_item_no} Cancelled by  {info.context.user}"
                )
                order.save()
            else:
                OrderLines.objects.filter(
                    id__in=[item.id for item in container_special_plant_items]
                ).delete()
                order_lines = order.orderlines_set.all()
                if not order_lines:
                    order.product_group = None
                user = info.context.user
                order.update_by = user
                order.save()
                logging.info(
                    f"[Export: Cancel/Delete] Item {list_item_no} Deleted by  {user}"
                )

        sap_order_messages += es_21_sap_order_messages
        sap_item_messages += es_21_sap_item_messages
        logging.error(
            f"[Export: Cancel/Delete] sap_order_error_header_messages: {sap_order_messages},"
            f"sap_item_error_messages: {sap_item_messages} from ES21"
        )
        return i_plan_messages, sap_order_messages, sap_item_messages

    except Exception as e:
        logging.error(f"[Export: Cancel/Delete] An Exception occurred: {str(e)}")
        transaction.set_rollback(True)
        raise ValueError(e)


def get_material_description_from_order_line(order_line):
    try:
        material = sap_master_data_models.MaterialMaster.objects.filter(
            material_code=order_line.material_variant.code
        ).first()
        return material.description_en
    except Exception:
        return ""


def get_material_variant_description_en_from_order_line(order_line):
    try:
        material = MaterialVariantMaster.objects.filter(
            code=order_line.material_variant.code
        ).first()
        return material and material.description_en or ""
    except Exception:
        return ""


def get_sales_unit_from_order_line(order_line):
    try:
        return order_line.contract_material.weight_unit
    except Exception:
        return ""


def get_qty_ton_from_order_line(order_line):
    try:
        quantity = order_line.quantity
        material_code = order_line.material_variant.code
        conversion = sap_master_data_models.Conversion2Master.objects.filter(
            material_code=material_code, to_unit="ROL"
        ).last()
        calculation = conversion.calculation
        order_quantity_ton = float(quantity) * float(calculation) / 1000
        return f"{order_quantity_ton:.3f}"
    except Exception:
        return f"{order_line.quantity:.3f}"


def get_address_from_order(order, partner_role):
    try:
        sold_to_code = order.contract.sold_to.sold_to_code
        sold_to_channel_partner = (
            sap_master_data_models.SoldToChannelPartnerMaster.objects.filter(
                sold_to_code=sold_to_code, partner_role=partner_role
            ).first()
        )
        address_link = sold_to_channel_partner.address_link
        partner_code = sold_to_channel_partner.partner_code
        sold_to_partner_address = (
            sap_master_data_models.SoldToPartnerAddressMaster.objects.filter(
                sold_to_code=sold_to_code,
                address_code=address_link,
                partner_code=partner_code,
            ).first()
        )

        address = (
            f"{sold_to_partner_address.street} {sold_to_partner_address.district} "
            f"{sold_to_partner_address.city} {sold_to_partner_address.postal_code}"
        )

        return address
    except Exception:
        return ""


def get_partner_from_order_for_sending_email(partner_code):
    try:
        sold_to_partner_address = (
            sap_master_data_models.SoldToPartnerAddressMaster.objects.filter(
                partner_code=partner_code,
            ).first()
        )

        return get_name_address_from_sold_to_partner(sold_to_partner_address)
    except Exception:
        return {"address": "", "name": ""}


def get_sold_to_name_and_address_from_order_for_sending_email(sold_to):
    try:
        sold_to_partner_address = get_sold_to_partner(sold_to)
        if not sold_to_partner_address:
            return {"address": "", "name": ""}
        return get_name_address_from_sold_to_partner(sold_to_partner_address)
    except Exception:
        return {"address": "", "name": ""}


def get_name_address_from_sold_to_partner(sold_to_partner_address):
    address_attrs = [
        sold_to_partner_address.street,
        sold_to_partner_address.street_sup1,
        sold_to_partner_address.street_sup2,
        sold_to_partner_address.street_sup3,
        sold_to_partner_address.district,
        sold_to_partner_address.city,
        sold_to_partner_address.postal_code,
    ]
    address_attrs = [attr if attr else "" for attr in address_attrs]
    address = " ".join(address_attrs)

    name_attrs = [
        sold_to_partner_address.name1,
        sold_to_partner_address.name2,
        sold_to_partner_address.name3,
        sold_to_partner_address.name4,
    ]

    name_attrs = [attr if attr else "" for attr in name_attrs]
    name = " ".join(name_attrs)

    return {"address": address, "name": name}


def get_contract_no_name_from_order(order):
    try:
        contract = order.contract
        contract_no_name = ""
        if contract.code and not contract.project_name:
            contract_no_name = contract.code
        if not contract.code and contract.project_name:
            contract_no_name = contract.project_name
        if contract.code and contract.project_name:
            contract_no_name = f"{contract.code} - {contract.project_name}"
        return contract_no_name
    except Exception:
        return ""


def get_sold_to_no_name_from_order(order):
    try:
        return f"{order.contract.sold_to.sold_to_code} {order.contract.sold_to.sold_to_name}"
    except Exception:
        return ""


def get_po_number_from_order(order):
    if order.type == "domestic" or order.type == "customer":
        po_number = order.po_number
    else:
        po_number = order.po_no
    return po_number if po_number else ""


def download_pdf_change_order(order_id, sort_type, created_by):
    try:
        order = Order.objects.filter(Q(id=order_id) | Q(so_no=order_id)).first()
        if not order:
            manager = get_plugins_manager()
            response = call_sap_es26(so_no=order_id, sap_fn=manager.call_api_sap_client)
            order = sync_export_order_from_es26(response)
        order_id = order.id
        order_lines = (
            OrderLines.objects.filter(order_id=order_id)
            .annotate(
                fkn_int_cast=Cast("item_no", output_field=IntegerField()),
            )
            .order_by(
                "-fkn_int_cast"
                if sort_type == "DESC" or sort_type == "desc"
                else "fkn_int_cast",
                "pk",
            )
        )
        created_user = order.created_by
        # if not created_user:
        #     created_user = created_by
        data = [
            {
                "item_no": order_line.item_no,
                "material_description": get_alternated_material_related_data(
                    order_line, get_material_description_from_order_line(order_line)
                ),
                "qty": (
                    f"{order_line.quantity:.3f}"
                    if order_line.quantity
                    and SalesUnitEnum.is_qty_conversion_to_decimal(
                        order_line.sales_unit
                    )
                    else int(order_line.quantity)
                    if order_line.quantity
                    else 0
                ),
                "sales_unit": order_line.sales_unit,
                "qty_ton": format_sap_decimal_values_for_pdf(order_line.net_weight_ton),
                "request_delivery_date": order_line.original_request_date.strftime(
                    "%d.%m.%Y"
                )
                if order_line.original_request_date
                else "",
                "iplan_confirm_date": order_line.request_date.strftime("%d.%m.%Y")
                if order_line.request_date
                else "",
                "message": "",
                "material_code": order_line.material.material_code,
            }
            for order_line in order_lines
        ]
        sales_unit, total_qty, total_qty_ton = get_summary_details_from_data(data)
        # data = sorted(
        #     data,
        #     key=lambda x: int(x.get("item_no") or 0),
        #     reverse=True if sort_type == "DESC" or sort_type == "desc" else False,
        # )
        # OLD DATE
        # dt_string = (
        #     timezone.now()
        #     .astimezone(pytz.timezone("Asia/Bangkok"))
        #     .strftime("%d/%m/%Y %H:%M:%S")
        # )
        # date should comes from created_at
        ship_to = order.ship_to and order.ship_to.split("\n")
        date_now = datetime.now().strftime("%d%m%Y")
        file_name_pdf = f"{order.so_no}{order.contract.sold_to.sold_to_code}{date_now}"
        template_pdf_data = {
            "po_no": get_po_number_from_order(order),
            "sale_org_name": get_sale_org_name_from_order(order),
            "so_no": order.so_no,
            "file_name": order.po_upload_file_log.file_name
            if order.po_upload_file_log
            else "",
            "date_time": convert_date_time_to_timezone_asia(order.saved_sap_at),
            "sold_to_no_name": get_sold_to_no_name(order.contract.sold_to.sold_to_code),
            "sold_to_address": get_address_from_order(order, "AG"),
            "ship_to_no_name": ship_to and ship_to[0] or "",
            "ship_to_address": ship_to[1] if ship_to and len(ship_to) == 2 else "",
            "payment_method_name": get_payment_method_name_from_order(order),
            "contract_no_name": get_contract_no_name_from_order(order),
            "remark_order_info": get_order_remark_order_info(order),
            "created_by": f"{created_user.first_name if created_user else ''} {created_user.last_name if created_user else ''}",
            "errors": [],
            "data": data,
            "total_qty": total_qty,
            "total_qty_ton": total_qty_ton,
            "sales_unit": sales_unit,
            "file_name_pdf": file_name_pdf or "Example",
            "print_date_time": get_date_time_now_timezone_asia(),
            "message": "",
        }
        pdf = html_to_pdf(template_pdf_data, "header.html", "content.html")
        base64_file = base64.b64encode(pdf)
        if order.order_no:
            return f"{order.order_no}.pdf", base64_file.decode("utf-8")
        else:
            return "order.pdf", base64_file.decode("utf-8")
    except Exception as e:
        raise ValueError(e)


def validate_when_status_is_partial_delivery(
    order, order_line, input_order_line, input_order=None
):
    """
    Validate data update when order's status is Partial Delivery.
    If not valid, raise ValidationError exception.
    """
    input_order = input_order or dict()
    if order.status != ScgOrderStatus.PARTIAL_DELIVERY.value:
        return

    invalid_fields = []
    # check plant field
    if "plant" in input_order_line and order_line.plant != input_order_line.get(
        "plant"
    ):
        invalid_fields.append("plant")

    # check quantity field
    if "quantity" in input_order_line and order_line.quantity != input_order_line.get(
        "quantity"
    ):
        invalid_fields.append("quantity")

    # check request date field
    if (
        "request_date" in input_order
        and order.request_date != input_order.get("request_date")
    ) or (
        "request_date" in input_order_line
        and order_line.request_date != input_order_line.get("request_date")
    ):
        invalid_fields.append("request_date")

    if invalid_fields:
        raise ValidationError(
            {
                "partial_delivery_related_error": ValidationError(
                    f"Cannot change {', '.join(invalid_fields)} if order's status is Partial Delivery",
                    code=ScgpExportErrorCode.INVALID.value,
                )
            }
        )


def change_parameter_of_export(order_line_id):
    try:
        distribution_channel_code = None
        order_line = OrderLines.objects.filter(id=order_line_id).first()
        if order_line and order_line.order and order_line.order.distribution_channel:
            distribution_channel_code = order_line.order.distribution_channel.code
        if distribution_channel_code:
            if int(distribution_channel_code) == 30:
                drop_down = InquiryMethodType.EXPORT.value
                return [drop_down, InquiryMethodType.ASAP.value]

        else:
            raise ValueError("Invalid distribution_channel code")

    except Exception:
        raise ValueError("Internal server error")


def update_inquiry_method_export(order_line_id, inquiry_method):
    try:
        order_line = OrderLines.objects.filter(id=order_line_id).first()
        order_line.inquiry_method = inquiry_method
        order_line.save()

        return order_line
    except Exception:
        raise ValueError("Internal server error")


def mock_confirmed_date(order):
    import calendar

    from dateutil.relativedelta import relativedelta
    from django.utils import timezone

    order_lines = OrderLines.objects.filter(
        order=order,
        return_status__in=[
            IPLanResponseStatus.UNPLANNED.value.upper(),
            IPLanResponseStatus.TENTATIVE.value.upper(),
        ],
        confirmed_date=None,
    )
    iplans = []
    for order_line in order_lines:
        request_date = order_line.request_date or timezone.now().date()
        two_month_later = request_date + relativedelta(months=+2)
        last_day_of_target_month = calendar.monthrange(
            two_month_later.year, two_month_later.month
        )[1]
        order_line.confirmed_date = timezone.datetime(
            year=two_month_later.year,
            month=two_month_later.month,
            day=last_day_of_target_month,
        ).date()

        # TODO: deal this redundant fields when refactor code
        iplan = order_line.iplan
        iplan.iplant_confirm_date = order_line.confirmed_date
        iplans.append(iplan)
    OrderLines.objects.bulk_update(order_lines, ["confirmed_date"])
    OrderLineIPlan.objects.bulk_update(iplans, ["iplant_confirm_date"])


def remove_cart_from_orderline(order_lines):
    cart_item_ids = []
    cart_id = None
    for order_line in order_lines:
        cart_item = order_line.cart_item
        cart_item_id = order_line.cart_item_id
        cart_item_ids.append(cart_item_id)
        if cart_item:
            cart_id = cart_item.cart_id

    if len(cart_item_ids):
        CartLines.objects.filter(id__in=cart_item_ids).delete()
        Cart.objects.filter(id=cart_id).annotate(
            num_cart_lines=Count("cartlines")
        ).filter(num_cart_lines=0).delete()


def _call_i_plan_delete_items(plugins, order_lines, so_no, order=None):
    log_opts = {
        "orderid": order and order.id or "",
        "order_number": so_no,
    }
    try:
        request_body = _prepare_param_i_plan_delete(order_lines, so_no)
        response = MulesoftApiRequest.instance(
            service_type=MulesoftServiceType.IPLAN.value, **log_opts
        ).request_mulesoft_post(IPlanEndPoint.I_PLAN_REQUEST.value, request_body)
        response_headers = response.get("DDQResponse").get("DDQResponseHeader")
        return response_headers
    except Exception as e:
        raise ValueError(e)


def _prepare_param_i_plan_delete(order_lines, so_no):
    request_line = [
        {
            "lineNumber": line.item_no,
            "locationCode": line.order.sold_to.sold_to_code,
            "productCode": get_product_code(line),
            "requestDate": line.request_date.strftime("%Y-%m-%dT00:00:00.000Z")
            if line.request_date
            else "",
            "inquiryMethod": IPlanInquiryMethodCode.JITCP.value,
            "quantity": str(line.quantity),
            "unit": "ROL",
            "transportMethod": "Truck",
            "typeOfDelivery": "E",
            "singleSourcing": False,
            "requestType": "DELETE",
        }
        for line in order_lines
    ]

    request_header_items = {
        "headerCode": so_no.lstrip("0"),
        "autoCreate": False,
        "DDQRequestLine": request_line,
    }
    request_header = [request_header_items]

    params = {
        "DDQRequest": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQRequestHeader": request_header,
        }
    }
    return params


def _call_es_21_delete_items(plugins, order_lines_object, order, so_no, status):
    params = _prepare_es_21_delete_cancel_order(
        order_lines_object, order, so_no, status
    )
    log_val = {"orderid": order.id, "order_number": order.so_no}
    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.SAP.value, **log_val
    ).request_mulesoft_post(SapEnpoint.ES_21.value, params)
    return response


def _prepare_es_21_delete_cancel_order(order_lines_object, order, so_no, status):
    ref_doc = order.contract.code
    order_items_in = [
        {
            "itemNo": line.item_no.zfill(6),
            "material": get_product_code(line),
            "targetQty": line.quantity,
            "salesUnit": "EA" if line.item_cat_eo == ItemCat.ZKC0.value else "ROL",
            "reasonReject": "93",
            "refDoc": ref_doc,
            "refDocIt": line.contract_material.item_no.zfill(6)
            if line.contract_material
            else line.ref_doc_it.zfill(6),
        }
        for line in order_lines_object
    ]

    order_items_inx = [
        {
            "itemNo": line.item_no.zfill(6),
            "updateflag": "U"
            if status == ChangeExportRejectReason.CANCEL_93.value
            else "D",
            "reasonReject": True,
        }
        for line in order_lines_object
    ]

    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": so_no,
        "testrun": False,
        "orderHeaderIn": {"refDoc": ref_doc},
        "orderItemsIn": order_items_in,
        "orderItemsInx": order_items_inx,
    }

    return params


def _get_iplan_atp_ctp_error_message(line, so_no):
    return_code = line.get("returnCode")
    if not return_code:
        return {
            "so_no": so_no,
            "item_no": line.get("lineNumber", "").lstrip("0"),
            "first_code": "0",
            "second_code": "0",
            "message": line.get("returnCodeDescription"),
        }
    return {
        "so_no": so_no,
        "item_no": line.get("lineNumber", "").lstrip("0"),
        "first_code": return_code[18:24],
        "second_code": return_code[24:32],
        "message": line.get("returnCodeDescription"),
    }


def _update_reject_reason_for_items(order_lines):
    update_line = []
    for line in order_lines:
        line.reject_reason = "93"
        line.item_status_en = IPlanOrderItemStatus.CANCEL.value
        line.item_status_th = (
            IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
                IPlanOrderItemStatus.CANCEL.value
            )
        )
        line.attention_type = None
        update_line.append(line)
    OrderLines.objects.bulk_update(
        update_line,
        fields=["reject_reason", "item_status_en", "item_status_th", "attention_type"],
    )


def make_surname_for_send_order_email(sold_to_code):
    text_line = ""
    sold_to_text_master = sap_master_data_models.SoldToTextMaster.objects.filter(
        sold_to_code=sold_to_code, text_id="Z008"
    )
    if sold_to_text_master.exists():
        sold_to_text_master_en = sold_to_text_master.filter(language="EN").first()
        sold_to_text_master = (
            sold_to_text_master_en
            if sold_to_text_master_en
            else sold_to_text_master.first()
        )

        text_line = (
            sold_to_text_master.text_line if sold_to_text_master.text_line else ""
        )

    return text_line
