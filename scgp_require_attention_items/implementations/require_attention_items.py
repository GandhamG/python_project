import copy
import datetime
import logging

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import F

from sap_migration import models as sap_migrations_models
from scg_checkout.graphql.enums import IPlanOrderStatus
from scg_checkout.graphql.helper import update_order_status
from scg_checkout.graphql.resolves.orders import call_sap_es26
from scgp_export.graphql.enums import ScgpExportOrder
from scgp_export.graphql.helper import handle_item_no_flag, sync_export_order_from_es26
from scgp_export.implementations.orders import validate_when_status_is_partial_delivery
from scgp_require_attention_items.error_codes import ScgpRequireAttentionItemsErrorCode
from scgp_require_attention_items.graphql.helper import (
    add_class_mark_into_order_line,
    append_field,
    is_valid_param_e21,
    send_params_to_es21,
    sort_values,
    stamp_class_mark_for_require_attention_change_request_date,
)
from scgp_require_attention_items.graphql.resolvers.require_attention_items import (
    get_order_line_and_type,
)
from scgp_require_attention_items.implementations.edit_order import (
    request_api_change_order,
)


def sync_order_prices(order_id):
    order = sap_migrations_models.Order.objects.filter(id=order_id).first()
    if order:
        line_total_prices = (
            sap_migrations_models.OrderLines.objects.filter(order_id=order_id)
            .exclude(item_status_en__in=[IPlanOrderStatus.CANCEL.value])
            .values_list("net_price", flat=True)
        )
        if None not in line_total_prices:
            total_price = sum(line_total_prices)
            tax_amount = float(total_price) * ScgpExportOrder.TAX.value
            order.net_price = float(total_price)
            order.tax_amount = tax_amount
            order.total_price = float(total_price) + tax_amount
            order.updated_at = datetime.datetime.now
            order.save()
    return order


@transaction.atomic
def delete_require_attention_items(unique_ids, info, reason_for_reject):
    try:
        order_lines = sap_migrations_models.OrderLines.objects.filter(id__in=unique_ids)
        order_ids = order_lines.values_list("order_id", flat=True).distinct()

        update_lines = []
        # TODO: Call ES21 to cancel order_lines but right now the database have not sync with the SAP API so we
        #       cannot test successfully for all the order lines so i'm gonna ignore the status in the response for this
        #       sprint
        dict_params_es21 = {}
        list_params_es21 = (
            sap_migrations_models.OrderLines.objects.filter(id__in=unique_ids)
            .values("order__so_no")
            .annotate(item_no=F("item_no"))
            .annotate(code=F("material_variant__code"))
        )
        if list_params_es21:
            for param in list_params_es21:
                if is_valid_param_e21(param):
                    key = param.get("order__so_no")
                    if key not in dict_params_es21:
                        dict_params_es21[key] = []
                    dict_params_es21[key].append(
                        {
                            "item_no": param.get("item_no"),
                            "material_variant_code": param.get("code"),
                        }
                    )
            manager = info.context.plugins
            if dict_params_es21:
                for key, value in dict_params_es21.items():
                    send_params_to_es21(key, value, manager, reason_for_reject)
        for order_line in order_lines:
            cancelled_status = IPlanOrderStatus.CANCEL.value
            order_line.item_status_en = cancelled_status
            order_line.item_status_th = (
                IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(cancelled_status)
            )
            update_lines.append(order_line)

        sap_migrations_models.OrderLines.objects.bulk_update(
            update_lines, fields=["item_status_en", "item_status_th"]
        )

        need_update_orders = []
        qs_orders = sap_migrations_models.Order.objects.filter(id__in=order_ids)
        for order in qs_orders:
            sync_order_prices(order.id)
            status_en, status_thai = update_order_status(order.id)
            order.status = status_en
            order.status_thai = status_thai
            need_update_orders.append(order)
        sap_migrations_models.Order.objects.bulk_update(
            need_update_orders,
            fields=[
                "status",
                "status_thai",
            ],
        )

        return True
    except Exception:
        transaction.set_rollback(True)
        raise ImproperlyConfigured("Internal Server Error!")


@transaction.atomic
def update_require_attention_item_parameter(order_line_id, params):
    try:
        order_line_i_plan = sap_migrations_models.OrderLineIPlan.objects.filter(
            orderlines__id=order_line_id
        )
        if not order_line_i_plan:
            new_order_line_i_plan = sap_migrations_models.OrderLineIPlan(
                inquiry_method_code=params.get("inquiry_method_code", None),
                transportation_method=params.get("transportation_method", None),
                type_of_delivery=params.get("type_of_delivery", None),
                fix_source_assignment=params.get("fix_source_assignment", None),
                split_order_item=params.get("split_order_item", None),
                partial_delivery=params.get("partial_delivery", None),
                consignment=params.get("consignment", None),
            )
            new_order_line_i_plan.save()
            order_line = sap_migrations_models.OrderLines.objects.get(id=order_line_id)
            order_line.iplan = new_order_line_i_plan
            order_line.save()
            return new_order_line_i_plan
        else:
            order_line_i_plan.update(**params)
            return order_line_i_plan.first()
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


@transaction.atomic
def accept_confirm_date(lines, info):
    try:
        if len(lines) < 1:
            raise ValueError("Please input data")
        else:
            order_line_ids = [line["unique_id"] for line in lines]
            success_id = order_line_ids[0]
            success_request_date = lines[0]["request_date"]
            today = datetime.date.today()
            if success_request_date and success_request_date < today:
                raise ValidationError(
                    {
                        "request_date": ValidationError(
                            "Request date must be further than today",
                            code=ScgpRequireAttentionItemsErrorCode.INVALID.value,
                        )
                    }
                )
            order_line = sap_migrations_models.OrderLines.objects.filter(
                id=success_id
            ).first()

            pre_update_items = sap_migrations_models.OrderLines.objects.filter(
                id=success_id
            ).in_bulk(field_name="id")
            origin_order_lines = [copy.deepcopy(order_line)]

            # don't allow change request_date if order's status is Partial Delivery
            validate_when_status_is_partial_delivery(
                order_line.order, order_line, lines[0]
            )

            order_line.request_date = lines[0]["request_date"]
            stamp_class_mark_for_require_attention_change_request_date(True, order_line)
            if success_request_date == order_line.confirmed_date:
                add_class_mark_into_order_line(order_line, "C1", "C", 1, 4)
            order_line.save()

            # Call i-plan update order
            updated_order_lines = [order_line]
            manager = info.context.plugins
            logging.info("Calling request_api_change_order method")
            response = request_api_change_order(
                order_line.order,
                manager,
                origin_order_lines,
                updated_order_lines,
                pre_update_lines=pre_update_items,
                export_delete_flag=False,
                only_update=True,
            )
            if not response.get("success"):
                raise ImproperlyConfigured("Cannot update order to SAP.")

            failed = []
            if lines[1:]:
                list_order_line_id = [line.get("unique_id") for line in lines[1:]]
                failed = sap_migrations_models.OrderLines.objects.filter(
                    id__in=list_order_line_id
                )
            else:
                pass
            success = sap_migrations_models.OrderLines.objects.filter(
                id__iexact=success_id
            ).first()
            if success:
                success_request_date = success.confirmed_date
                update_attention_type_accept_confirmed_date(
                    success, success_request_date
                )
                success.request_date = success_request_date
                success.save()
            return [[success], failed] if failed else [[success], []]
    except Exception as e:
        transaction.set_rollback(True)
        logging.error(e)
        if isinstance(e, ValidationError):
            raise e
        raise ImproperlyConfigured("Internal server error")


def update_attention_type_accept_confirmed_date(order_line, request_date):
    attention_type = order_line.attention_type
    attention_type_comma = attention_type.count(",")
    confirmed_date = order_line.confirmed_date
    if request_date == confirmed_date and (
        "R1" in attention_type if attention_type else False
    ):
        if attention_type_comma > 0:
            new_attention_type = order_line.attention_type.replace("R1, ", "")
            order_line.attention_type = new_attention_type
        else:
            new_attention_type = order_line.attention_type.replace("R1", "")
            order_line.attention_type = new_attention_type
    if request_date != confirmed_date:
        attention_type = append_field(attention_type, "R1")
        attention_type = sort_values(attention_type, 1, 4, "R")
        order_line.attention_type = attention_type
    order_line.save()


def update_request_date_attention_type(success_item):
    if success_item.type == "export":
        success_order_line_export = sap_migrations_models.OrderLines.objects.filter(
            id=success_item.order_line_id
        ).first()
        success_order_line_export.request_date = (
            success_order_line_export.confirmed_date
        )
        success_order_line_export.save()
        update_attention_type_accept_confirmed_date(
            success_order_line_export, success_order_line_export.request_date
        )
    if success_item.type == "domestic":
        success_order_line_domestic = sap_migrations_models.OrderLines.objects.filter(
            id=success_item.order_line_id
        ).first()
        success_order_line_domestic.request_date = (
            success_order_line_domestic.confirmed_date
        )
        success_order_line_domestic.save()
        update_attention_type_accept_confirmed_date(
            success_order_line_domestic,
            success_order_line_domestic.request_date,
        )


def change_parameter_i_plan(order_line_id):
    try:
        order_line, order_line_type = get_order_line_and_type(order_line_id)
        drop_down = ""
        if order_line_type == "domestic":
            drop_down = "Domestic"
        elif order_line_type == "export":
            drop_down = "Export"
        else:
            distribution_channel_value = get_distribution_channel_of_order_line(
                order_line
            )
            if distribution_channel_value:
                if int(distribution_channel_value) == 30:
                    drop_down = "Export"
                elif (
                    int(distribution_channel_value) == 10
                    or int(distribution_channel_value) == 20
                ):
                    drop_down = "Domestic"
                else:
                    raise ValueError("Invalid distribution_channel_value")
        return [drop_down, "ASAP (Clear stock)"]
    except Exception:
        raise ValueError("Internal server error")


def get_distribution_channel_of_order_line(order_line):
    try:
        return order_line.order.distribution_channel.code
    except Exception:
        return None


def parameter_inquiry(
    order_line_id,
    inquiry_method_code,
    use_inventory,
    use_consignment_inventory,
    use_projected_inventory,
    use_production,
    order_split_logic,
    single_source,
):
    order_line_response = {
        "lineNumber": order_line_id,
        "inquiryMethod": inquiry_method_code,
        "useInventory": use_inventory,
        "useConsignmentInventory": use_consignment_inventory,
        "useProjectedInventory": use_projected_inventory,
        "useProduction": use_production,
        "orderSplitLogic": order_split_logic,
        "singleSourcing": single_source,
    }
    return order_line_response


def pass_parameter_to_i_plan(order_line_id, inquiry_method):
    try:
        order_line = sap_migrations_models.OrderLines.objects.get(id=order_line_id)
        order_line.inquiry_method = inquiry_method
        order_line.save()
        return True
    except Exception:
        raise ValueError("Internal Server Error")


def update_order_line(lines, list_data):
    for line in lines:
        data = next((x for x in list_data if int(x["id"]) == line.id), {})
        if not data.get("id", None):
            continue
        data["id"] = int(data["id"])
        line.__dict__.update(**data)
    return lines


@transaction.atomic
def edit_require_attention_items(lines, info):
    manager = info.context.plugins
    try:
        params = info.variable_values
        success = []
        failed = []
        orders, order_lines, line_dict = handle_input_order_lines(lines)
        for order in orders:
            failed, success = handle_edit_success_failed(
                order_lines, order, lines, manager, failed, success, line_dict, params
            )

            so_no = order.so_no
            response = call_sap_es26(so_no=so_no, sap_fn=manager.call_api_sap_client)
            sync_export_order_from_es26(response)
        return success, failed

    except Exception as e:
        transaction.set_rollback(True)
        logging.error(e)
        if isinstance(e, ValidationError):
            raise e
        raise ImproperlyConfigured("Internal server error")


@transaction.atomic
def handle_edit_success_failed(
    order_lines, order, lines, manager, failed, success, line_dict, params
):
    origin_order_lines, updated_order_lines, response = handle_success_failed(
        order_lines, order, lines, manager, params
    )

    if not response.get("success"):
        failed = get_message_response(origin_order_lines, failed, response, line_dict)
    else:
        success = get_message_response(
            updated_order_lines, success, response, line_dict
        )
        sap_migrations_models.OrderLines.objects.bulk_update(
            updated_order_lines, ["request_date", "quantity"]
        )
    return failed, success


def handle_input_order_lines(lines):
    line_dict = {int(line["id"]): line for line in lines}
    if not lines:
        raise ValueError("Please input data")
    order_lines = sap_migrations_models.OrderLines.objects.filter(
        id__in=map(lambda x: x["id"], lines)
    )
    orders = list(map(lambda x: x.order, order_lines))
    orders_list = list(dict.fromkeys(orders))
    return orders_list, order_lines, line_dict


@transaction.atomic
def accept_confirm_date_items(lines, info):
    manager = info.context.plugins
    try:
        params = info.variable_values
        success = []
        failed = []
        orders, order_lines, _ = handle_input_order_lines(lines)
        for order in orders:
            failed, success = handle_accept_confirm_result(
                order_lines,
                order,
                lines,
                manager,
                failed,
                success,
                params,
            )
            so_no = order.so_no
            response = call_sap_es26(so_no=so_no, sap_fn=manager.call_api_sap_client)
            sync_export_order_from_es26(response)
        return success, failed

    except Exception as e:
        transaction.set_rollback(True)
        logging.error(e)
        if isinstance(e, ValidationError):
            raise e
        raise ImproperlyConfigured("Internal server error")


@transaction.atomic
def handle_success_failed(
    order_lines,
    order,
    lines,
    manager,
    params,
    accept_confirm_date=False,
):
    line_of_order = order_lines.filter(order_id=order.id)
    origin_order_lines = copy.deepcopy(line_of_order)
    pre_update_items = sap_migrations_models.OrderLines.objects.filter(
        order=order
    ).in_bulk(field_name="id")
    updated_order_lines = update_order_line(line_of_order, lines)
    item_no_flags = handle_item_no_flag(order, params)
    logging.info("Calling request_api_change_order method")
    response = request_api_change_order(
        order,
        manager,
        origin_order_lines,
        updated_order_lines,
        accept_confirm_date,
        sap_update_flag=item_no_flags,
        updated_data={},
        pre_update_lines=pre_update_items,
        export_delete_flag=False,
        only_update=True,
        require_attention=True,
    )
    return origin_order_lines, updated_order_lines, response


def handle_accept_confirm_result(
    order_lines, order, lines, manager, failed, success, params
):
    origin_order_lines, updated_order_lines, response = handle_success_failed(
        order_lines, order, lines, manager, params, accept_confirm_date=True
    )
    if not response.get("success"):
        failed = get_message_response(origin_order_lines, failed, response, {})
    else:

        for line in updated_order_lines:
            line.request_date = line.confirmed_date
            stamp_class_mark_for_require_attention_change_request_date(True, line)
            add_class_mark_into_order_line(line, "C1", "C", 1, 4)
            line.save()
        success = get_message_response(updated_order_lines, success, response, {})
    return failed, success


def get_message_response(list_order_lines, list_response, response, line_dict):
    for order_line in list_order_lines:
        list_response.append(
            {
                "order_no": order_line.order.so_no,
                "item_no": order_line.item_no,
                "material_code": order_line.material_variant.code,
                "material_description": order_line.material_variant.description_th,
                "request_date": order_line.request_date,
                "original_quantity": order_line.quantity,
                "request_quantity": line_dict.get(order_line.id, {}).get("quantity")
                or order_line.quantity,
                "original_request_date": line_dict.get(order_line.id, {}).get(
                    "request_date"
                )
                or order_line.original_request_date,
                "confirm_date": order_line.confirmed_date,
                "confirm_quantity": order_line.iplan.iplant_confirm_quantity,
                "sap_order_messages": response.get("sap_order_messages"),
                "sap_item_messages": response.get("sap_item_messages"),
            }
        )
    return list_response
