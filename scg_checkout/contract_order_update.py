import base64
import copy
import logging
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime
from functools import reduce

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import IntegerField, Q
from django.db.models.functions import Cast
from django.utils import timezone

import sap_migration.models
from common.helpers import format_sap_decimal_values_for_pdf, net_price_calculation
from common.product_group import SalesUnitEnum
from sap_master_data import models as master_models
from sap_migration import models as migration_models
from sap_migration.graphql.enums import OrderType
from sap_migration.models import OrderLines
from scg_checkout.error_codes import ContractCheckoutErrorCode
from scg_checkout.graphql.helper import (
    get_alternated_material_related_data,
    get_summary_details_from_data,
    is_other_product_group,
)
from scgp_export.implementations.orders import (
    deduct_quantity_cart_item,
    get_material_description_from_order_line,
    remove_cart_from_orderline,
    validate_when_status_is_partial_delivery,
)
from scgp_export.implementations.sap import get_web_user_name
from scgp_po_upload.graphql.helpers import html_to_pdf
from scgp_require_attention_items.graphql.helper import (
    add_class_mark_into_order_line,
    update_attention_type_r1,
    update_attention_type_r3,
)

from .graphql.enums import (
    IPlanOrderItemStatus,
    IPLanResponseStatus,
    ItemDetailsEdit,
    OrderEdit,
    ReasonForChangeRequestDateDescriptionEnum,
    SapUpdateFlag,
    ScgOrderStatus,
)
from .graphql.helper import (
    call_yt65838_split_order,
    convert_date_time_to_timezone_asia,
    deepget,
    deepgetattr,
    get_date_time_now_timezone_asia,
    get_id_of_object_model_from_code,
    update_order_lines_item_status_en_and_item_status_th,
    update_order_product_group,
)
from .graphql.implementations.iplan import (
    call_i_plan_create_order,
    get_order_remark_order_info_for_print_preview_order,
    get_payment_method_name_from_order,
    get_sale_org_name_from_order,
    get_sold_to_no_name,
    request_api_change_order,
    request_i_plan_delete_cancel_order,
)
from .graphql.implementations.sap import (
    es_21_delete_cancel_order,
    get_error_messages_from_sap_response_for_change_order,
)


def contract_order_lines_update(order_lines, order):
    return_order_lines = []
    for order_line in order_lines:
        remark = get_remark_through_domestic_order_line_id(order_line["id"])
        object_line = migration_models.OrderLines.objects.filter(
            id=order_line.get("id")
        ).first()
        validate_when_status_is_partial_delivery(order, object_line, order_line)

        object_line.plant = order_line.get("plant")
        object_line.quantity = order_line.get("quantity")
        object_line.net_price = order_line.get("net_price")
        object_line.request_date = order_line.get("request_date")
        object_line.internal_comments_to_warehouse = order_line.get(
            "internal_comments_to_warehouse"
        )
        object_line.shipping_mark = order_line.get("shipping_mark")
        object_line.external_comments_to_customer = order_line.get(
            "external_comments_to_customer"
        )
        object_line.internal_comments_to_logistic = order_line.get(
            "internal_comments_to_logistic"
        )
        object_line.ship_to = order_line.get("ship_to")
        object_line.product_information = order_line.get("product_information")
        add_class_mark_into_order_line(object_line, remark, "C", 1, 4)
        object_line.po_no = order_line.get("po_no", object_line.po_no)
        object_line.po_no_external = order_line.get(
            "po_no_external", object_line.po_no_external
        )
        object_line.delivery_tol_over = order_line.get(
            "delivery_tol_over", object_line.delivery_tol_over
        )
        object_line.delivery_tol_under = order_line.get(
            "delivery_tol_under", object_line.delivery_tol_under
        )
        object_line.delivery_tol_unlimited = order_line.get(
            "delivery_tol_unlimited", object_line.delivery_tol_unlimited
        )
        object_line.weight_unit = order_line.get("weight_unit")
        object_line.plant = order_line.get("plant")
        object_line.original_quantity = order_line.get(
            "original_quantity", object_line.original_quantity
        )
        object_line.shipping_point = order_line.get(
            "shipping_point", object_line.shipping_point
        )
        object_line.route = order_line.get("route", object_line.route)
        object_line.item_cat_eo = order_line.get(
            "item_category", object_line.item_cat_eo
        )
        object_line.total_weight = order_line.get("quantity") * (
            object_line.weight if object_line.weight else 1
        )
        object_line.request_date_change_reason = order_line.get(
            "request_date_change_reason"
        )
        if not object_line.original_request_date:
            object_line.original_request_date = order_line.get("request_date")
        object_line.save()
        return_order_lines.append(object_line)
    return return_order_lines


@transaction.atomic
def contract_order_update(order_id_input, params, info):
    try:
        logging.info(
            f"[Domestic create order] for Order id: {order_id_input} , FE request payload: {params}"
            f" by user: {info.context.user}"
        )
        order_information = params.pop("order_information")
        order_organization_data = params.pop("order_organization_data")
        status = params.get("status")
        order_id = order_id_input
        if len(order_id) < 10:
            order = migration_models.Order.objects.get(id=order_id)
        else:
            order = migration_models.Order.objects.filter(so_no=order_id).first()

        original_order = deepcopy(order)
        order_id = order.id

        validate_when_status_is_partial_delivery(order, None, {}, order_information)

        order.po_date = order_information.get("po_date", order.po_date)
        order.po_number = order_information.get("po_number", order.po_number)
        order.po_no = order_information.get("po_number", order.po_number)
        order.ship_to = order_information.get("ship_to", order.ship_to)
        order.bill_to = order_information.get("bill_to", order.bill_to)
        order.order_type = order_information.get("order_type", order.order_type)
        order.request_date = order_information.get("request_date", order.request_date)
        order.customer_group_1_id = (
            get_id_of_object_model_from_code(
                migration_models.CustomerGroup1Master.objects,
                order_information.get("customer_group_1_id"),
            )
            or order.customer_group_1_id
        )
        order.customer_group_2_id = (
            get_id_of_object_model_from_code(
                migration_models.CustomerGroup2Master.objects,
                order_information.get("customer_group_2_id"),
            )
            or order.customer_group_2_id
        )
        order.customer_group_3_id = (
            get_id_of_object_model_from_code(
                migration_models.CustomerGroup3Master.objects,
                order_information.get("customer_group_3_id"),
            )
            or order.customer_group_3_id
        )
        order.customer_group_4_id = (
            get_id_of_object_model_from_code(
                migration_models.CustomerGroup4Master.objects,
                order_information.get("customer_group_4_id"),
            )
            or order.customer_group_4_id
        )
        order.external_comments_to_customer = order_information.get(
            "external_comments_to_customer", order.external_comments_to_customer
        )
        order.internal_comments_to_warehouse = order_information.get(
            "internal_comments_to_warehouse", order.internal_comments_to_warehouse
        )
        order.internal_comments_to_logistic = order_information.get(
            "internal_comments_to_logistic", order.internal_comments_to_logistic
        )
        order.product_information = order_information.get(
            "product_information", order.product_information
        )
        order.shipping_point = order_information.get(
            "shipping_point", order.shipping_point
        )
        order.route = order_information.get("route", order.route)
        order.delivery_block = order_information.get(
            "delivery_block", order.delivery_block
        )

        incoterms_code = order_information.get("incoterms_id", order.incoterms_1_id)

        incoterms_1_master = master_models.Incoterms1Master.objects.filter(
            code=incoterms_code
        ).first()
        if incoterms_1_master is not None:
            incoterms_1_id = incoterms_1_master.id
        else:
            incoterms_1_id = order.incoterms_1_id

        order.incoterms_1_id = incoterms_1_id

        order.sales_organization_id = order_organization_data.get(
            "sale_organization_id", order.sales_organization_id
        )
        order.distribution_channel_id = order_organization_data.get(
            "distribution_channel_id", order.distribution_channel_id
        )
        order.division_id = order_organization_data.get(
            "division_id", order.division_id
        )
        order.sales_group_id = order_organization_data.get(
            "sale_group_id", order.sales_group_id
        )
        order.sales_office_id = order_organization_data.get(
            "sale_office_id", order.sales_office_id
        )
        order.updated_by = info.context.user

        order_type = None
        distribution_code = master_models.DistributionChannelMaster.objects.get(
            pk=order.distribution_channel_id
        ).code
        if distribution_code in ["10", "20"]:
            order_type = OrderType.DOMESTIC
        elif distribution_code == "30":
            order_type = OrderType.EXPORT

        if order_type is not None:
            order.web_user_name = get_web_user_name(
                order_type=order_type, user=info.context.user
            )

        # UPDATE ORDER LINE
        order_line_ids = []
        split_item_ids = []
        split_item_info = {}

        order_lines_info = params.get("lines")
        update_item_no(order_id, order_lines_info)
        sap_update_flag = unmark_draft_and_delete_not_used_orderlines(
            [str(line.get("item_no")) for line in order_lines_info], order.id
        )

        for order_line in order_lines_info:
            order_line_ids.append(order_line.get("id"))
            for item in order_line.get("split_items", []):
                split_item_info[str(item.id)] = item
                split_item_ids.append(item.id)

        order_line_objects = {}
        split_item_objects = {}
        for order_line in migration_models.OrderLines.objects.filter(
            pk__in=order_line_ids
        ):
            order_line_objects[str(order_line.id)] = order_line

        for order_line in migration_models.OrderLines.objects.filter(
            original_order_line_id__in=order_line_ids
        ).order_by("id"):
            if (
                str(order_line.id) in order_line_ids
                and sap_update_flag.get(order_line.item_no) == "I"
            ):
                if (
                    split_item_objects.get(str(order_line.original_order_line_id))
                    is None
                ):
                    split_item_objects[str(order_line.original_order_line_id)] = [
                        order_line
                    ]
                else:
                    split_item_objects[str(order_line.original_order_line_id)].append(
                        order_line
                    )

        order_lines = []
        split_order_lines = []
        list_line_ids = []
        total_price = 0

        for order_line in order_lines_info:
            order_line_id = str(order_line.get("id"))
            order_product_grp = order_line_objects[order_line_id].prc_group_1
            original_quantity = order_line_objects[order_line_id].original_quantity
            new_line_quantity = original_quantity
            orderline_split_items = split_item_objects.get(order_line_id)
            if orderline_split_items is not None and len(orderline_split_items) > 0:
                """if orderline item is having split item, we will update the split item only"""
                """and re-calculate the original item quantity"""
                for split_obj in orderline_split_items:
                    quantity = split_item_info.get(str(split_obj.id)).get(
                        "quantity", split_obj.quantity
                    )
                    request_date = split_item_info.get(str(split_obj.id)).get(
                        "request_date", split_obj.request_date
                    )
                    item_line = {
                        "id": split_obj.id,
                        "quantity": quantity,
                        "net_price": net_price_calculation(
                            order_product_grp,
                            quantity,
                            split_obj.contract_material.price_per_unit,
                            split_obj.weight if split_obj.weight else 1,
                        ),
                        "request_date": request_date,
                        "internal_comments_to_warehouse": split_obj.internal_comments_to_warehouse,
                        "ship_to": split_obj.ship_to,
                        "product_information": split_obj.product_information,
                        "shipping_mark": split_obj.shipping_mark,
                        "over_delivery_tol": split_obj.over_delivery_tol,
                        "under_delivery_tol": split_obj.under_delivery_tol,
                        "weight_unit": split_obj.weight_unit,
                    }
                    total_price += item_line.get("net_price")
                    new_line_quantity -= quantity
                    split_order_lines.append(item_line)
            else:
                """If there aren't any split, update the original quantity only"""
                new_line_quantity = order_line.get(
                    "quantity", order_line_objects[order_line_id].quantity
                )
                original_quantity = new_line_quantity

            list_line_ids.append(order_line_id)
            line = {
                "id": order_line_id,
                "plant": order_line.get(
                    "plant", order_line_objects[order_line_id].plant
                ),
                "quantity": new_line_quantity,
                "original_quantity": original_quantity,
                "net_price": net_price_calculation(
                    order_product_grp,
                    new_line_quantity,
                    order_line_objects[order_line_id].contract_material.price_per_unit,
                    order_line_objects[order_line_id].weight
                    if order_line_objects[order_line_id].weight
                    else 1,
                ),
                "request_date": order_line.get(
                    "request_date", order_line_objects[order_line_id].request_date
                ),
                "internal_comments_to_warehouse": order_line.get(
                    "internal_comments_to_warehouse",
                    order_line_objects[order_line_id].internal_comments_to_warehouse,
                ),
                "external_comments_to_customer": order_line.get(
                    "external_comments_to_customer",
                    order_line_objects[order_line_id].external_comments_to_customer,
                ),
                "internal_comments_to_logistic": order_line.get(
                    "internal_comments_to_logistic",
                    order_line_objects[order_line_id].internal_comments_to_logistic,
                ),
                "ship_to": order_line.get(
                    "ship_to", order_line_objects[order_line_id].ship_to
                ),
                "product_information": order_line.get(
                    "product_information",
                    order_line_objects[order_line_id].product_information,
                ),
                "shipping_mark": order_line.get(
                    "shipping_mark", order_line_objects[order_line.id].shipping_mark
                ),
                "delivery_tol_over": order_line.get(
                    "over_delivery_tol",
                    order_line_objects[order_line_id].delivery_tol_over,
                ),
                "delivery_tol_under": order_line.get(
                    "under_delivery_tol",
                    order_line_objects[order_line_id].delivery_tol_under,
                ),
                "delivery_tol_unlimited": order_line.get(
                    "delivery_tol_unlimited",
                    order_line_objects[order_line_id].delivery_tol_unlimited,
                ),
                "po_no": order_line.get(
                    "po_no",
                    order_line_objects[order_line_id].po_no,
                ),
                "po_no_external": order_line.get(
                    "po_no_external",
                    order_line_objects[order_line_id].po_no_external,
                ),
                "weight_unit": order_line.get(
                    "weight_unit", order_line_objects[order_line_id].weight_unit
                ),
                "shipping_point": order_line.get(
                    "shipping_point", order_line_objects[order_line_id].shipping_point
                ),
                "route": order_line.get(
                    "route", order_line_objects[order_line_id].route
                ),
                "item_category": order_line.get(
                    "item_category", order_line_objects[order_line_id].item_category
                ),
                "request_date_change_reason": order_line.get(
                    "request_date_change_reason",
                    order_line_objects[order_line_id].request_date_change_reason,
                ),
            }
            total_price += line.get("net_price")
            order_lines.append(line)
        origin_order_lines = list(
            migration_models.OrderLines.objects.filter(id__in=list_line_ids)
        )

        tax_percent = get_tax_percent(order.sold_to.sold_to_code)
        tax_amount = total_price * tax_percent
        total_price_inc_tax = total_price + tax_amount
        order.total_price = total_price
        order.total_price_inc_tax = total_price_inc_tax
        order.tax_amount = tax_amount

        updated_order_lines = contract_order_lines_update(order_lines, order)

        """Split will use their own query to update"""
        """This will need to update after confirmation on SEO-977"""
        contract_order_lines_update(split_order_lines, order)

        order_line_ids.extend(split_item_ids)
        contract_order_lines_delete_exclude(order_line_ids, order_id)

        checkout_order_lines = migration_models.OrderLines.objects.filter(
            order_id=order_id
        )

        success = True
        sap_order_messages = []
        sap_item_messages = []
        i_plan_messages = []
        warning_messages = []
        if (
            order.status == ScgOrderStatus.PRE_DRAFT.value
            and status == ScgOrderStatus.DRAFT.value
        ):
            order.status = status
            deduct_quantity_cart_item(order_id, info.context.user)
            remove_cart_from_orderline(checkout_order_lines)

        if (
            order.status in (ScgOrderStatus.DRAFT.value, ScgOrderStatus.PRE_DRAFT.value)
            and status == ScgOrderStatus.CONFIRMED.value
        ):
            # Case create order
            if is_order_contract_project_name_special(order):
                OrderLines.objects.filter(order=order).update(class_mark="C1")
            manage = info.context.plugins

            dict_order_lines_info = {x["id"]: x for x in order_lines_info}
            logging.info("calling call_i_plan_create_order method")
            response = call_i_plan_create_order(
                order,
                manage,
                user=info.context.user,
                ui_order_lines_info=dict_order_lines_info,
            )

            if response.get("success"):
                order.status = response.get("order_status")
                order.so_no = response.get("sap_order_number")
                update_order_lines_item_status_en_and_item_status_th(
                    order,
                    checkout_order_lines,
                    IPlanOrderItemStatus.ITEM_CREATED.value,
                    IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
                        IPlanOrderItemStatus.ITEM_CREATED.value
                    ),
                )
                order.created_at = timezone.now()
                update_field_call_atp_ctp_for_order_lines(checkout_order_lines)
            else:
                success = False

            order.created_at = timezone.now()
            order.status_sap = response.get("sap_order_status")
            sap_order_messages = response.get("sap_order_messages")
            sap_item_messages = response.get("sap_item_messages")
            i_plan_messages = response.get("i_plan_messages")
            warning_messages = response.get("warning_messages")

        elif order.status not in (
            ScgOrderStatus.DRAFT.value,
            ScgOrderStatus.PRE_DRAFT.value,
        ):
            # Case update order
            logging.error(
                f"Duplicate order creation request found. An order already exists with the same SO No {order.so_no}"
            )
            raise ValidationError(
                {
                    "create_order": ValidationError(
                        f"Duplicate order creation request found. An order already exists with the same SO No {order.so_no}",
                        code=ContractCheckoutErrorCode.DUPLICATE_ORDER.value,
                    )
                }
            )
            manager = info.context.plugins
            response = request_api_change_order(
                order,
                manager,
                origin_order_lines,
                updated_order_lines,
                sap_update_flag=sap_update_flag,
                original_order=original_order,
            )
            if not response.get("success"):
                success = False
            sap_order_messages = response.get("sap_order_messages")
            sap_item_messages = response.get("sap_item_messages")

        # Rollback when call API fail
        if not success:
            transaction.set_rollback(True)
        else:
            order.save()
            # Update attention type
            attention_order_lines = migration_models.OrderLines.objects.filter(
                order_id=order_id
            ).select_related("iplan", "order")
            update_attention_type_r1(attention_order_lines)
            update_attention_type_r3(attention_order_lines)
            OrderLines.objects.bulk_update(
                attention_order_lines, fields=["attention_type"]
            )

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
            f"  ValidationError {e}while creating Domestic order for Order id: {order_id_input}"
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
            f"  Exception {e} while creating Domestic order for Order id: {order_id_input}"
            f" by user: {info.context.user}"
        )
        transaction.set_rollback(True)
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)


def unmark_draft_and_delete_not_used_orderlines(order_line_item_nos, order_id):
    new_order_line_item_nos = migration_models.OrderLines.all_objects.filter(
        item_no__in=order_line_item_nos, draft=True, order_id=order_id
    ).values_list("item_no", flat=True)

    sap_update_flag = {}
    for item_no in order_line_item_nos:
        item_no = str(item_no)
        if item_no in new_order_line_item_nos:
            sap_update_flag[item_no] = SapUpdateFlag.INSERT.value
        else:
            sap_update_flag[item_no] = SapUpdateFlag.UPDATE.value

    migration_models.OrderLines.all_objects.filter(
        item_no__in=order_line_item_nos,
        order_id=order_id,
    ).update(draft=False)
    return sap_update_flag


def get_tax_percent(sold_to_code):
    sold_to_channel = master_models.SoldToChannelMaster.objects.filter(
        sold_to_code=sold_to_code
    ).first()

    # Not found tax value
    if sold_to_channel is None:
        return 0

    taxkd = sold_to_channel.taxkd

    # IF taxkd value equal 1, tax will be 7%, else there won't be tax
    if taxkd == "1":
        return 0.07
    else:
        return 0


@transaction.atomic
def contract_order_delete(order_id):
    try:
        migration_models.OrderLines.objects.filter(order_id=order_id).delete()
        return migration_models.Order.objects.filter(id=order_id).delete()
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


@transaction.atomic
def delete_contract_order_drafts():
    try:
        order_ids = migration_models.Order.objects.filter(
            status__in=("draft", "pre-draft")
        ).values_list("id")
        order_line_ids = migration_models.OrderLines.objects.filter(
            order_id__in=order_ids
        ).values_list("id")

        migration_models.OrderLines.objects.filter(pk__in=order_line_ids).delete()

        return migration_models.Order.objects.filter(pk__in=order_ids).delete()
    except Exception as ex:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(ex)


def contract_order_line_delete(id):
    return migration_models.OrderLines.objects.filter(id=id).delete()


@transaction.atomic
def contract_order_lines_delete(ids):
    try:
        order_lines_del = migration_models.OrderLines.objects.filter(pk__in=ids)
        order_id = order_lines_del.first().order_id
        result = order_lines_del.delete()
        order_lines = migration_models.OrderLines.objects.filter(
            order_id=order_id
        ).order_by("pk")
        item_no = 10
        order_lines_update = []
        for order_line in order_lines:
            order_line.item_no = item_no
            order_lines_update.append(order_line)
            item_no += 10
        if not order_lines:
            update_order_product_group(order_id, None)
        order_lines.bulk_update(order_lines_update, ["item_no"])
        return result
    except Exception as e:
        transaction.set_rollback(True)
        if isinstance(e, ValidationError):
            raise e
        raise ImproperlyConfigured(e)


def contract_order_lines_delete_exclude(ids, order_id):
    return (
        migration_models.OrderLines.objects.filter(order_id=order_id)
        .exclude(pk__in=ids)
        .delete()
    )


def is_order_contract_project_name_special(order: sap_migration.models.Order) -> bool:
    project_name = order.contract.project_name or ""
    if len(project_name) < 2:
        return False
    if project_name[0:2] in ["DS", "DG", "DW"]:
        return True

    return False


def get_remark_through_domestic_order_line_id(order_line_id):
    order_line = migration_models.OrderLines.objects.filter(id=order_line_id).first()
    project_name = order_line.contract_material.contract.project_name
    if project_name:
        if len(project_name) < 2:
            return
        if project_name[0:2] in ("DS", "DG", "DW"):
            return "C1"
        else:
            return
    else:
        logging.info(
            f"[Create Order] project name came as None for order line id {order_line_id}"
        )


def check_update_fields(update_fields, data):
    fields_update = []
    for update_field in update_fields:
        if data[update_field]:
            fields_update.append(update_field)
    return fields_update


@transaction.atomic
def order_lines_update(order_id, data):
    try:
        request_date = data["request_date"]
        bill_to = data["bill_to"]
        external_comments_to_customer = data["external_comments_to_customer"]
        internal_comments_to_warehouse = data["internal_comments_to_warehouse"]
        internal_comments_to_logistic = data["internal_comments_to_logistic"]
        product_information = data["product_information"]
        shipping_point = data["shipping_point"]
        route = data["route"]

        update_fields = [
            "request_date",
            "bill_to",
            "external_comments_to_customer",
            "internal_comments_to_warehouse",
            "internal_comments_to_logistic",
            "product_information",
            "shipping_point",
            "route",
        ]

        update_fields = check_update_fields(update_fields, data)
        order = migration_models.Order.objects.get(id=order_id)
        if order.status == ScgOrderStatus.CONFIRMED.value:
            raise Exception("Confirmed order can not change status")

        order_lines = migration_models.OrderLines.objects.filter(order_id=order_id)
        order_lines_ids = [order_line.id for order_line in order_lines]

        list_order_lines_update = []
        for order_lines_id in order_lines_ids:
            validate_when_status_is_partial_delivery(
                order,
                next(item for item in order_lines if item.id == order_lines_id),
                data,
            )

            order_line_update = migration_models.OrderLines(
                id=order_lines_id,
                request_date=request_date,
                bill_to=bill_to,
                external_comments_to_customer=external_comments_to_customer,
                internal_comments_to_warehouse=internal_comments_to_warehouse,
                internal_comments_to_logistic=internal_comments_to_logistic,
                product_information=product_information,
                shipping_point=shipping_point,
                route=route,
            )
            list_order_lines_update.append(order_line_update)

        if list_order_lines_update:
            migration_models.OrderLines.objects.bulk_update(
                list_order_lines_update,
                update_fields,
            )
        return order

    except Exception as e:
        transaction.set_rollback(True)
        if isinstance(e, ValidationError):
            raise e
        raise ImproperlyConfigured(e)


def contract_order_line_all_update(data):
    order_lines = migration_models.OrderLines.objects.filter(order_id=data["id"])
    order = order_lines[0].order if order_lines else None
    for lines in order_lines:
        validate_when_status_is_partial_delivery(order, lines, data)

        if data.get("plant"):
            lines.plant = data.get("plant")
        if data.get("request_date"):
            lines.request_date = data.get("request_date")
    migration_models.OrderLines.objects.bulk_update(
        order_lines, ["plant", "request_date"]
    )

    return order_lines


def _mapping_order(prev: dict, next: OrderLines):
    if prev.get(next.order.so_no, None):
        prev.get(next.order.so_no).append(next)
    else:
        prev.update({next.order.so_no: [next]})
    return prev


@transaction.atomic
def cancel_revert_contract_order_lines(data, info):
    try:
        order_lines_ids = data.get("order_line_ids")
        status = data.get("reason").get("reason_for_reject")
        (
            success_lines_dict,
            failed_lines_dict,
            failed_lines_messages,
        ) = ({}, {}, {})
        special_item_call_es_21_dict = defaultdict(list)
        success, failed, failed_item_result, item_call_es_21_list = [], [], [], []
        special_plants = ["754F", "7531", "7533"]
        manager = info.context.plugins

        order_lines_special_plant = migration_models.OrderLines.objects.filter(
            id__in=order_lines_ids, plant__in=special_plants
        )

        for line in order_lines_special_plant:
            order_no = line.order.so_no
            special_item_call_es_21_dict[order_no].append({"lineNumber": line.item_no})

        if len(order_lines_special_plant) == len(order_lines_ids):
            item_call_es_21_list = _handle_list_to_dict_items(
                special_item_call_es_21_dict, {}
            )
            success, failed = es_21_delete_cancel_order(
                item_call_es_21_list,
                status,
                manager,
            )
            return success, failed

        order_lines_call_i_plan = (
            migration_models.OrderLines.objects.select_related("order")
            .filter(id__in=order_lines_ids)
            .exclude(plant__in=special_plants)
        )
        mapped_orders = reduce(
            lambda prev, next: _mapping_order(prev, next),
            list(order_lines_call_i_plan),
            {},
        )

        call_i_plan_request_delete = request_i_plan_delete_cancel_order(
            mapped_orders, manager
        )
        response_line = call_i_plan_request_delete.get("DDQResponse").get(
            "DDQResponseHeader"
        )

        for lines in response_line:
            header_code = lines.get("headerCode").zfill(10)
            ddq_response_line = lines.get("DDQResponseLine")
            success_lines_dict[header_code] = _mapped_response_status(
                ddq_response_line, IPLanResponseStatus.SUCCESS.value.lower()
            )
            failed_messages = _mapped_response_status(
                ddq_response_line, IPLanResponseStatus.FAILURE.value.lower()
            )
            failed_lines_dict[header_code] = failed_messages
            if failed_messages:
                for item in failed_messages:
                    failed_lines_messages[
                        f"{header_code.zfill(10)}-{item.get('lineNumber')}"
                    ] = item.get("returnCodeDescription")

        if not _check_dict_has_none_value(failed_lines_dict):
            failed_item_result = _handle_fail_item_i_plan(
                failed_lines_dict, failed_item_result, failed_lines_messages
            )

        if not _check_dict_has_none_value(success_lines_dict):
            item_call_es_21_list = _handle_list_to_dict_items(
                special_item_call_es_21_dict, success_lines_dict
            )
            success, failed = es_21_delete_cancel_order(
                item_call_es_21_list,
                status,
                manager,
            )
        failed += failed_item_result

        return sorted(success, key=lambda x: (x["order_no"], x["item_no"])), sorted(
            failed, key=lambda x: (x["order_no"], x["item_no"])
        )
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def _mapped_response_status(response_line, response):
    result = list(
        filter(
            lambda order: order.get("returnStatus", "").lower() == response,
            response_line,
        )
    )
    if not result:
        result = None
    return result


def _get_message_response_iplan(line, message):
    return {
        "order_no": line.order.so_no,
        "item_no": line.item_no,
        "material_code": line.material_variant.code,
        "material_description": line.material_variant.description_th,
        "request_date": line.request_date,
        "confirm_date": line.confirmed_date,
        "confirm_quantity": line.iplan.iplant_confirm_quantity,
        "message": message,
    }


def get_sales_unit_from_order_line(order_line):
    return deepgetattr(order_line, "sales_unit", "")


def get_address_from_order(order, partner_role):
    try:
        sold_to_code = order.contract.sold_to.sold_to_code
        sold_to_channel_partner = (
            master_models.SoldToChannelPartnerMaster.objects.filter(
                sold_to_code=sold_to_code,
                partner_code=sold_to_code,
                partner_role=partner_role,
            ).first()
        )
    except AttributeError:
        return None
    if sold_to_channel_partner:
        address_link = sold_to_channel_partner.address_link
        partner_code = sold_to_channel_partner.partner_code
        sold_to_partner_address = (
            master_models.SoldToPartnerAddressMaster.objects.filter(
                sold_to_code=sold_to_code,
                address_code=address_link,
                partner_code=partner_code,
            ).first()
        )
        if not sold_to_partner_address:
            return None
        address = (
            f"{sold_to_partner_address.street} {sold_to_partner_address.district} "
            f"{sold_to_partner_address.city} {sold_to_partner_address.postal_code}"
        )

        return address
    return None


def get_po_number_from_order(order):
    if order.type == "domestic" or order.type == "customer":
        po_number = order.po_number
    else:
        po_number = order.po_no
    return po_number if po_number else ""


def print_change_order(order_id, sort_type):
    try:
        order_header_msg = ""
        sort_direction = "fkn_int_cast"
        if sort_type in ("DESC", "desc"):
            sort_direction = "-fkn_int_cast"
        order = migration_models.Order.objects.get(Q(id=order_id) | Q(so_no=order_id))
        order_lines = (
            migration_models.OrderLines.objects.filter(
                Q(order_id=order_id) | Q(order__so_no=order_id)
            )
            .exclude(status=IPlanOrderItemStatus.CANCEL.value)
            .annotate(
                fkn_int_cast=Cast("item_no", output_field=IntegerField()),
            )
            .order_by(
                sort_direction,
                "pk",
            )
        )
        created_by = order.created_by
        sold_to = order.sold_to
        contract = order.contract
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
                "sales_unit": get_sales_unit_from_order_line(order_line),
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
        ship_to = order.ship_to.split("\n") if order.ship_to else [""]
        date_now = datetime.now().strftime("%d%m%Y")
        file_name_pdf = f"{order.so_no}{sold_to.sold_to_code}{date_now}"
        contract_no_name = (
            f"{contract.code} - {contract.project_name}"
            if contract.code and contract.project_name
            else contract.code or contract.project_name or ""
        )
        sales_unit, total_qty, total_qty_ton = get_summary_details_from_data(data)
        template_pdf_data = {
            "po_no": get_po_number_from_order(order),
            "sale_org_name": get_sale_org_name_from_order(order),
            "so_no": order.so_no,
            "file_name": "",
            "date_time": convert_date_time_to_timezone_asia(order.created_at),
            "sold_to_no_name": get_sold_to_no_name(sold_to.sold_to_code),
            "sold_to_address": get_address_from_order(order, "AG"),
            "ship_to_no_name": ship_to[0],
            "ship_to_address": ship_to[1] if len(ship_to) == 2 else "",
            "payment_method_name": get_payment_method_name_from_order(order),
            "contract_no_name": contract_no_name,
            "remark_order_info": get_order_remark_order_info_for_print_preview_order(
                order
            ),
            "created_by": f"{created_by.first_name if created_by else ''} {created_by.last_name if created_by else ''}",
            "errors": [],
            "data": data,
            "total_qty": total_qty,
            "total_qty_ton": total_qty_ton,
            "sales_unit": sales_unit,
            "file_name_pdf": file_name_pdf or "Example",
            "print_date_time": get_date_time_now_timezone_asia(),
            "message": order_header_msg,
        }
        pdf = html_to_pdf(template_pdf_data, "header.html", "content.html")
        base64_file = base64.b64encode(pdf)
        return f"{order.order_no or 'order'}.pdf", base64_file.decode("utf-8")

    except Exception as e:
        raise ValueError(e)


def add_split_order_line_item(so_no, origin_item, split_items, info):
    success = True
    split_items_db = []
    split_iplans_db = []
    order_line_db = migration_models.OrderLines.objects.get(pk=origin_item.get("id"))
    response = call_yt65838_split_order(
        so_no, origin_item, split_items, order_line_db, info
    )
    (
        sap_order_message,
        sap_item_message,
        is_being_process,
        sap_success,
    ) = get_error_messages_from_sap_response_for_change_order(response)

    # TODO once mulesoft add SAP response based on it below logic will be revisit

    if sap_order_message or sap_item_message:
        logging.info(
            f"[Domestic Split item] so_no: {so_no}, sap_order_error_message: {sap_order_message},"
            f"sap_item_error_message: {sap_item_message}"
        )
        error = []
        for err in sap_order_message:
            error.append(f"{err.get('error_code')} - {err.get('error_message')}")
        for err in sap_item_message:
            error.append(
                f"{err.get('item_no')} - {err.get('error_code')} - {err.get('error_message')}"
            )
        error_message = "\n".join(error)

        error_src = "SAP"
        raise ValidationError(
            {
                error_src: ValidationError(
                    error_message,
                    code=ContractCheckoutErrorCode.NOT_FOUND.value,
                ),
                "error_src": error_src,
            }
        )

    logging.info(
        f"[Domestic Split item] so_no: {so_no},"
        f" original item_no: {order_line_db.item_no},"
        f"DB original quantity: {order_line_db.quantity}, "
        f"DB original assigned_quantity: {order_line_db.assigned_quantity}"
    )
    order_line_db.quantity = origin_item.get("quantity")
    dict_order_schedules_out = {}
    if response:
        order_schedules_outs = response.get("orderSchedulesOut", [])
    dict_order_schedules_out = {
        str(order_schedule["itemNo"]).lstrip("0"): order_schedule["confirmQuantity"]
        for order_schedule in order_schedules_outs
    }

    order_line_db.assigned_quantity = dict_order_schedules_out.get(
        str(origin_item.get("item_no")), 0
    )
    for item in split_items:
        split_item = copy.deepcopy(order_line_db)
        split_iplan = copy.deepcopy(order_line_db.iplan)
        split_item.pk = None
        split_iplan.pk = None
        split_item.iplan = split_iplan
        split_item.iplan.iplant_confirm_quantity = item.get("quantity", 0)
        split_item.origin_item = order_line_db
        split_item.quantity = item.get("quantity", 0)
        split_item.assigned_quantity = dict_order_schedules_out.get(
            str(item.get("item_no")), 0
        )
        split_item.item_no = item.get("item_no")
        split_item.request_date = item.get("request_date")
        split_items_db.append(split_item)
        split_iplans_db.append(split_iplan)

    order_line_db.iplan.iplant_confirm_quantity = origin_item.get("quantity", 0)
    order_line_db.iplan.save()
    order_line_db.save()
    migration_models.OrderLineIPlan.objects.bulk_create(split_iplans_db)
    migration_models.OrderLines.objects.bulk_create(split_items_db)

    return success, sap_order_message, sap_item_message


@transaction.atomic
def delete_split_order_line_item(split_item_id):
    try:
        split_item = migration_models.OrderLines.objects.get(pk=split_item_id)
        if split_item.original_order_line is None:
            raise Exception("Can't delete original orderline from order")
        original_item = migration_models.OrderLines.objects.get(
            pk=split_item.original_order_line_id
        )

        original_item.quantity += split_item.quantity
        original_item.net_price = (
            original_item.quantity * original_item.contract_material.price_per_unit
        )

        split_item.delete()
        original_item.save()

        return original_item
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


@transaction.atomic
def update_order_line(root, info, data):
    try:
        order_lines_input = data["input"]
        dict_lines = {line.get("id"): line for line in order_lines_input}
        order_lines = migration_models.OrderLines.objects.filter(
            id__in=dict_lines.keys()
        )

        order = order_lines[0].order if order_lines else None

        list_lines = []
        for line in order_lines:
            validate_when_status_is_partial_delivery(
                order, line, dict_lines.get(line.id)
            )

            if dict_lines.get(line.id).get("atp_ctp_status", "rollback") == "rollback":
                continue
            line.atp_ctp_status = dict_lines.get(line.id).get(
                "atp_ctp_status", line.atp_ctp_status
            )
            line.confirmed_date = dict_lines.get(line.id).get(
                "confirmed_date", line.confirmed_date
            )
            line.plant = dict_lines.get(line.id).get("plant", line.plant)
            if dict_lines.get(line.id).get("quantity", line.quantity) < line.quantity:
                line.quantity = dict_lines.get(line.id).get("quantity", line.quantity)

            order_line_i_plan = migration_models.OrderLineIPlan.objects.filter(
                id=line.iplan_id
            ).first()
            order_line_i_plan.atp_ctp = dict_lines.get(line.id).get(
                "atp_ctp", order_line_i_plan.atp_ctp
            )
            order_line_i_plan.atp_ctp_detail = dict_lines.get(line.id).get(
                "atp_ctp_detail", order_line_i_plan.atp_ctp_detail
            )
            order_line_i_plan.block = dict_lines.get(line.id).get(
                "block", order_line_i_plan.block
            )
            order_line_i_plan.run = dict_lines.get(line.id).get(
                "run", order_line_i_plan.run
            )
            order_line_i_plan.save()

            list_lines.append(line)

        migration_models.OrderLines.objects.bulk_update(
            list_lines, ["atp_ctp_status", "confirmed_date", "plant", "quantity"]
        )

        return True
    except Exception as e:
        transaction.set_rollback(True)
        if isinstance(e, ValidationError):
            raise e
        raise ImproperlyConfigured(e)


def mapping_item_no_to_order_line(order, item_nos):
    order_lines = migration_models.OrderLines.all_objects.filter(order=order).filter(
        item_no__in=item_nos
    )

    item_no_to_order_line = {}
    for item_no in item_nos:
        for order_line in order_lines:
            if item_no == order_line.item_no:
                item_no_to_order_line[item_no] = order_line

    return item_no_to_order_line


def update_field_call_atp_ctp_for_order_lines(checkout_order_lines):
    for order_line in checkout_order_lines:
        order_line.call_atp_ctp = True


def update_item_no(order_id, order_lines_info):
    order_line_ids = [line.get("id") for line in order_lines_info]
    id_to_order_line = migration_models.OrderLines.all_objects.filter(
        order_id=order_id, id__in=order_line_ids
    ).in_bulk()
    for line in order_lines_info:
        order_line = id_to_order_line[int(line.get("id"))]
        order_line.item_no = line.get("item_no", "").lstrip("0")

    migration_models.OrderLines.all_objects.bulk_update(
        id_to_order_line.values(), ["item_no"]
    )


def check_field_change(order_in_database, field_name_db, data_input, field_name_input):
    seen = {None, "", False}
    if not order_in_database:
        raise ValueError("Order does not exist")
    if field_name_input == "iplan_details.input_parameter" and str(
        deepget(data_input, field_name_input, "")
    ):
        value_in_database = deepgetattr(order_in_database, field_name_db, "")
        if (not value_in_database) and str(
            deepget(data_input, field_name_input, "")
        ) == "ASAP (Clear stock)":
            return False
        if value_in_database != str(deepget(data_input, field_name_input, "")):
            return True

    value_in_database = deepgetattr(order_in_database, field_name_db, "")
    ui_value = deepget(data_input, field_name_input, "")
    if field_name_db in {"delivery_tol_under", "delivery_tol_over"}:
        value_in_database = int(value_in_database) if value_in_database else 0
    if (
        value_in_database
        and isinstance(value_in_database, str)
        and field_name_db in {"ship_to", "bill_to"}
    ):
        value_in_database = value_in_database.split(" ")[0]
    if str(value_in_database) == str(deepget(data_input, field_name_input, "")) or (
        deepgetattr(order_in_database, field_name_db, "") in seen
        and deepget(data_input, field_name_input, "") in seen
    ):
        return False
    if (
        field_name_input == "order_information.reason_for_change_request_date"
        and value_in_database
        == ReasonForChangeRequestDateDescriptionEnum[
            deepget(data_input, field_name_input, "")
        ].value
    ):
        return False
    if isinstance(order_in_database, migration_models.Order):
        logging.info(
            f"[Domestic change order] Header Field {field_name_input.split('.')[1]} "
            f"db value: {value_in_database} from FE user changed to :{ui_value}"
        )
    else:
        logging.info(
            f"[Domestic change order] Item {order_in_database.item_no} Field {field_name_input.split('.')[1]} "
            f"db value: {value_in_database} from FE user changed to :{ui_value}"
        )

    return True


def mapping_change_order(order_in_database, data_input, need_iplan_integration):
    data_header = data_input.get("header", {})
    item_details_tab = data_input.get("item_details", [])
    result = {
        "order_header": {},
        "order_input": data_header,
        "order_in_database": order_in_database,
        "order_lines_new": {},
        "order_lines_update": {},
        "order_lines_split": {},
        "order_lines_cancel": {},
        "order_lines_input": {
            order_line["item_no"]: order_line for order_line in item_details_tab
        },
        "order_lines_in_database": {},
        "yt65217": {},
        "yt65156": {},
    }
    list_item_no = []
    for order_line in item_details_tab:
        list_item_no.append(order_line.get("item_no"))
    handle_field_change(
        order_in_database,
        data_header,
        OrderEdit.FIELDS_CHANGE.value,
        result["order_header"],
    )
    order_lines_in_database = (
        migration_models.OrderLines.objects.filter(
            order__so_no=order_in_database.so_no, item_no__in=list_item_no
        )
        .distinct("item_no")
        .in_bulk(field_name="item_no")
    )
    result["order_lines_in_database"] = order_lines_in_database
    for order_line_input in item_details_tab:
        item_no = order_line_input.get("item_no", None)
        if item_no in order_lines_in_database:
            result["order_lines_update"][item_no] = {}
            handle_field_change(
                order_lines_in_database[item_no],
                order_line_input,
                ItemDetailsEdit.FIELDS.value,
                result["order_lines_update"][item_no],
            )
            if not result["order_lines_update"][item_no]:
                del result["order_lines_update"][item_no]

            if result["order_lines_update"].get(item_no):
                check_item_status(
                    result, order_lines_in_database[item_no], item_no, order_line_input
                )
    update_inquiry_method(result, order_lines_in_database)

    if not need_iplan_integration:
        logging.debug(
            f"clearing the yt65217 and yt65156 since product belongs to K02/K09 SO No is: {order_in_database.so_no}"
        )
        result["yt65217"] = {}
        result["yt65156"] = {}
    return result


def change_order_item_scenario1(result, item_no):
    result["yt65156"][item_no] = result["order_lines_input"][item_no]


def change_order_item_scenario2(
    result, item_no, update_field, order_type, quantity_input, order_lines_in_db
):
    if not order_lines_in_db.assigned_quantity:
        order_lines_in_db.assigned_quantity = 0
    sap_func = "yt65156"
    if order_type == "CTP":
        if update_field.get("plant"):
            raise ValueError("Can't update plant")
        if update_field.get("quantity") or update_field.get("request_date"):
            if quantity_input > order_lines_in_db.quantity:
                raise ValueError(
                    "Can't increase quantity of order line CTP have item status over planning confirm"
                )
            if quantity_input < order_lines_in_db.assigned_quantity:
                raise ValueError(
                    "Can't update quantity of order line CTP have item status over planning confirm"
                )
        sap_func = "yt65217"
    logging.info(
        f"[Domestic change order] {sap_func}_items {item_no} as its status is {order_lines_in_db.item_status_en}"
    )
    result[sap_func][item_no] = result["order_lines_input"][item_no]


def change_order_item_scenario3(
    result,
    item_no,
    update_field,
    order_type,
    quantity_input,
    order_lines_in_db,
    request_date_input,
):
    today = date.today()
    sap_func = "yt65156"
    if order_type == "CTP":
        if update_field.get("plant"):
            raise ValueError("Can't update plant")
        if (
            update_field.get("quantity")
            and order_type == "CTP"
            and quantity_input > order_lines_in_db.quantity
        ):
            raise ValueError(
                "Can't increase quantity of order line CTP have item status is Completed Production"
            )
        if update_field.get("request_date") and request_date_input < today:
            raise ValueError(
                "Can't update request_date < confirm date of order line have item status is Completed Production"
            )

        sap_func = "yt65217"
    logging.info(
        f"[Domestic change order] {sap_func}_items {item_no} as its status is {order_lines_in_db.item_status_en}"
    )
    result[sap_func][item_no] = result["order_lines_input"][item_no]


def check_item_status(result, order_lines_in_database, item_no, order_line_input):
    item_status_rank = IPlanOrderItemStatus.IPLAN_ORDER_LINE_RANK.value
    item_status = order_lines_in_database.item_status_en
    prod_group = order_lines_in_database.material_group2
    request_date_input = datetime.strptime(
        order_line_input.order_information.request_date, "%d/%m/%Y"
    ).date()
    quantity_input = order_line_input.order_information.quantity
    order_type = order_lines_in_database.iplan.order_type
    update_field = result["order_lines_update"].get(item_no, {})
    logging.info(
        f"[Domestic change order] User updated item : {item_no} and its fields: {update_field} "
        f"and its DB item_status_en: {item_status}"
    )

    if item_status not in item_status_rank:
        raise ValueError(
            "Cannot change quantity or request date or plant of order line with invalid item status"
        )

    item_status_index = item_status_rank.index(item_status)
    update_fields = [
        "quantity",
        "plant",
        "request_date",
        "input_parameter",
        "consignment_location",
    ]
    if is_other_product_group(prod_group):
        logging.debug(
            f"[Domestic change order] Skipping validation for other product groups : {prod_group}"
        )
        return

    if any(update_field.get(field) for field in update_fields):
        if item_status_index < item_status_rank.index(
            IPlanOrderItemStatus.PLANNING_CLOSE_LOOP.value
        ) or item_status_index == item_status_rank.index(
            IPlanOrderItemStatus.PLANNING_OUTSOURCING.value
        ):
            change_order_item_scenario1(result, item_no)
            logging.info(
                f"[Domestic change order] yt65156_items {item_no} as its status is {item_status}"
            )
        elif item_status_index < item_status_rank.index(
            IPlanOrderItemStatus.FULL_COMMITTED_ORDER.value
        ):
            change_order_item_scenario2(
                result,
                item_no,
                update_field,
                order_type,
                quantity_input,
                order_lines_in_database,
            )
        elif item_status_index < item_status_rank.index(
            IPlanOrderItemStatus.PARTIAL_DELIVERY.value
        ):
            change_order_item_scenario3(
                result,
                item_no,
                update_field,
                order_type,
                quantity_input,
                order_lines_in_database,
                request_date_input,
            )
        else:
            raise ValueError(
                "Cannot change quantity or request date or plant of order line with item status over partial delivery"
            )

    elif item_status_index > item_status_rank.index(
        IPlanOrderItemStatus.PARTIAL_DELIVERY.value
    ) and not (
        item_status_index
        == item_status_rank.index(IPlanOrderItemStatus.COMPLETE_DELIVERY)
        and update_field.get("reason_for_change_request_date")
    ):
        raise ValueError(
            "Cannot change order line with item status over partial delivery"
        )


def handle_field_change(obj_in_database, input_data, mapping_fields, result):
    for field_name_db, field_name_input in mapping_fields.items():
        if field_name_input == "order_information.weight_unit":
            continue
        seen = {None, "", False}
        if field_name_input in ("order_information.request_date", "partner.po_date"):
            value_in_db = deepgetattr(
                obj_in_database, field_name_input.split(".")[1], ""
            )
            ui_value = deepget(input_data, field_name_input, "")
            if value_in_db:
                value_in_db = value_in_db.strftime("%d/%m/%Y")
            if value_in_db != ui_value and not (
                value_in_db in seen and ui_value in seen
            ):
                result[field_name_input.split(".")[-1]] = True
                if isinstance(obj_in_database, migration_models.Order):
                    logging.info(
                        f"[Domestic change order] Header Field {field_name_input.split('.')[1]} "
                        f"db value: {value_in_db} from FE user changed to :{ui_value}"
                    )
                else:
                    logging.info(
                        f"[Domestic change order] Item {obj_in_database.item_no} Field {field_name_input.split('.')[1]} "
                        f"db value: {value_in_db} from FE user changed to :{ui_value}"
                    )
            continue
        if check_field_change(
            obj_in_database, field_name_db, input_data, field_name_input
        ):
            result[field_name_input.split(".")[-1]] = True


def _handle_fail_item_i_plan(
    failed_lines_dict, failed_item_result, failed_lines_messages
):
    tmp = Q()
    for k, v in failed_lines_dict.items():
        line_nums = map(lambda item: item.get("lineNumber"), v)
        tmp |= Q(Q(order__so_no=k.zfill(10)) & Q(item_no__in=list(line_nums)))
    lines = OrderLines.objects.select_related("order").filter(tmp)

    for line in lines:
        key = f"{line.order.so_no}-{line.item_no}"
        if key in failed_lines_messages.keys():
            message = failed_lines_messages.get(key)
            failed_item_result.append(_get_message_response_iplan(line, message))
    return failed_item_result


def _handle_list_to_dict_items(dict_1, dict_2):
    dict_1 = defaultdict(list, dict_1)
    dict_2 = defaultdict(list, dict_2)
    dict_3 = {}

    for key in set(dict_1.keys()) | set(dict_2.keys()):
        value_1 = dict_1[key]
        value_2 = dict_2[key]
        line_numbers = [d["lineNumber"] for d in value_1 + value_2]
        dict_3[key] = line_numbers
    list_3 = [dict_3]
    return list_3


def _check_dict_has_none_value(my_dict):
    return any(value is None for value in my_dict.values())


def update_inquiry_method(result, order_lines_db):
    order_lines_input = result.get("order_lines_input")
    update_lines = []
    for item_no, item in order_lines_input.items():
        inquiry_method = (
            item.get("iplan_details", {}).get("input_parameter") or "Domestic"
        )
        order_line_db = order_lines_db.get(item_no, None)
        if order_line_db and order_line_db.inquiry_method != inquiry_method:
            logging.info(
                f"[Domestic change order] item {item_no} db inquiry_method: {order_line_db.inquiry_method} "
                f"updated to: {inquiry_method}"
            )
            order_line_db.inquiry_method = inquiry_method
            update_lines.append(order_line_db)
    sap_migration.models.OrderLines.objects.bulk_update(
        update_lines, ["inquiry_method"]
    )
