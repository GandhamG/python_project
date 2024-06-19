import logging
import time
from functools import reduce
from common.helpers import get_change_item_scenario, get_item_scenario, getattrd
from common.enum import ChangeItemScenario, ChangeOrderAPIFlow
from common.iplan.types import IPlanYT65156Message
from common.newrelic_metric import add_metric_process_order, force_update_attributes
import graphene
from saleor.graphql.core.mutations import BaseMutation
from sap_migration.graphql.enums import InquiryMethodType, OrderType
from sap_migration.models import Order, OrderLines
from typing import Dict, List, Tuple
from saleor.graphql.core.types import NonNullList
from scg_checkout.graphql.enums import IPlanOrderItemStatus, AtpCtpStatus
from django.db.models import F
from django.conf import settings

from scg_checkout.graphql.helper import validate_item_status_scenario2_3
from scg_checkout.graphql.implementations.sap import (
    get_sap_warning_messages,
    get_error_messages_from_sap_response_for_change_order)
from scg_checkout.graphql.resolves.orders import call_sap_es26
from scg_checkout.graphql.types import SapItemMessage, SapOrderMessage, WarningMessage
from scgp_export.graphql.enums import IPlanResponseStatus
from scgp_export.graphql.helper import sync_export_order_from_es26

from scgp_export.graphql.scgp_export_error import ScgpExportError
from scgp_export.implementations.es21 import request_es21_update_export_order
from scgp_export.implementations.yt65156 import (
    handle_yt65156_confirm,
    handle_yt65156_request,
    handle_yt65156_rollback,
    is_item_need_to_request_iplan,
)
from common.iplan.yt65156_helper import get_iplan_message, get_yt65217_message
from scgp_export.implementations.yt65217 import handle_yt65217_update_order
from scgp_export.implementations.edit_order import update_order_after_request_mulesoft
from scgp_require_attention_items.graphql.helper import update_attention_type_r5


# ---------------Input------------------------#


class EditExportOrderHeaderInput(graphene.InputObjectType):
    po_no = graphene.String()
    po_date = graphene.Date(description="PO Date")
    ref_pi_no = graphene.String()
    request_date = graphene.Date()
    usage = graphene.String()
    unloading_point = graphene.String()
    place_of_delivery = graphene.String()
    port_of_discharge = graphene.String()
    port_of_loading = graphene.String()
    no_of_containers = graphene.String()
    uom = graphene.String()
    gw_uom = graphene.String()
    etd = graphene.Date()
    eta = graphene.Date()
    dlc_expiry_date = graphene.Date()
    dlc_no = graphene.String()
    dlc_latest_delivery_date = graphene.Date()
    description = graphene.String()
    end_customer = graphene.String()
    shipping_mark = graphene.String()

    # Right tab
    ship_to = graphene.String()
    bill_to = graphene.String()
    payer = graphene.String()
    payment_instruction = graphene.String()
    remark = graphene.String()
    production_information = graphene.String()
    internal_comment_to_warehouse = graphene.String()


class EditOrderItemInput(graphene.InputObjectType):
    id = graphene.ID()

    quantity = graphene.Float()
    weight_unit = graphene.String()
    item_cat_eo = graphene.String()
    plant = graphene.String()
    ref_pi_stock = graphene.String()
    request_date = graphene.Date()

    route = graphene.String()
    delivery_tol_under = graphene.Float()
    delivery_tol_over = graphene.Float()
    delivery_tol_unlimited = graphene.Boolean()
    condition_group1 = graphene.String()
    roll_diameter = graphene.String()
    roll_core_diameter = graphene.String()
    roll_quantity = graphene.String()
    roll_per_pallet = graphene.String()
    pallet_size = graphene.String()
    pallet_no = graphene.String()
    package_quantity = graphene.String()
    packing_list = graphene.String()
    shipping_point = graphene.String()
    remark = graphene.String()
    inquiry_method = InquiryMethodType()
    shipping_mark = graphene.String()


class EditExportOrderInput(graphene.InputObjectType):
    so_no = graphene.String()
    order_header = graphene.Field(EditExportOrderHeaderInput)
    order_items = NonNullList(EditOrderItemInput)


# -------------End of input classes------------------------------------#

# --------------Helper functions----------------------------------------#


def get_order_header_updated_data(order: Order, order_header_data: dict) -> dict:
    updated_data = {}
    from .constants import ORDER_HEADER_FIELD_FROM_DB_TO_SAP

    mapping_fields = ORDER_HEADER_FIELD_FROM_DB_TO_SAP.keys()
    for key in mapping_fields:
        order_model_field_data = getattr(order, key, None)
        order_header_field_data = getattr(order_header_data, key, None)
        if key == 'etd':
            order_header_field_data = str(order_header_field_data)
        if not order_model_field_data and not order_header_field_data:
            continue
        if order_model_field_data != order_header_field_data:
            logging.info(f"[Export change order] order header updated field:{key},db value:{order_model_field_data},"
                         f"FE value:{order_header_field_data}")
            updated_data.update({key: order_header_field_data})
    return updated_data


def get_order_items_updated_data(
        order_items: Dict[str, OrderLines], order_items_data: List[dict]
) -> dict:
    items_updated_data: dict[str, dict] = {}

    for order_item_data in order_items_data:
        item_no = order_item_data.get("item_no")
        order_item_model = order_items.get(item_no)
        updated_data = {}

        if not order_item_model:
            continue

        for item_updated_key, item_updated_value in order_item_data.items():
            model_field = getattr(order_item_model, item_updated_key, None)
            if model_field != item_updated_value:
                updated_data.update({item_updated_key: item_updated_value})
        items_updated_data.update({item_no: {updated_data}})

    return items_updated_data


def get_item_api_flow(order_line: OrderLines) -> ChangeOrderAPIFlow:
    order_type = getattrd(order_line, "iplan.order_type")
    '''
    call YT-65156 based on Order Line IPlan order type value 
        1. Blank or Empty 
        2. ATP Future or ATP OnHand 
    '''
    if not order_type or order_type in [AtpCtpStatus.ATP_FUTURE.value, AtpCtpStatus.ATP_ON_HAND.value]:
        return ChangeOrderAPIFlow.YT65156
    if order_type == "CTP" and get_change_item_scenario(order_line) in [ChangeItemScenario.SCENARIO_2,
                                                                        ChangeItemScenario.SCENARIO_3]:
        return ChangeOrderAPIFlow.YT65217
    return ChangeOrderAPIFlow.YT65156



def check_item_status(order_lines_in_database, order_line_input):
    item_status_rank = IPlanOrderItemStatus.IPLAN_ORDER_LINE_RANK.value
    item_status = order_lines_in_database.item_status_en
    item_status_index = item_status_rank.index(item_status)
    if item_status_index > item_status_rank.index(
        IPlanOrderItemStatus.PARTIAL_DELIVERY.value
    ):
        raise ValueError(
            "Cannot change order line with item status over partial delivery"
        )



def get_items_by_item_status(
        items: Dict[int, OrderLines], order_items_data: Dict
) -> Tuple[Dict[int, OrderLines], Dict[int, OrderLines], Dict[int, OrderLines]]:
    yt65156_items = {}
    yt65217_items = {}
    items_without_iplan = {}
    for id, item in items.items():
        item_update_data = order_items_data.get(str(id))
        if not is_item_need_to_request_iplan(item, item_update_data):
            items_without_iplan[id] = item
            logging.info(f"[Export change order] items_without_iplan call as no fields modified: {item.item_no}")
            continue
        check_item_status(item,item_update_data)
        if get_item_api_flow(item) == ChangeOrderAPIFlow.YT65217:
            yt65217_items[id] = item
            logging.info(f"[Export change order] yt65217_items: {item.item_no} "
                         f"as its status is: {item.production_status}")
        else:
            yt65156_items[id] = item
            logging.info(f"[Export change order] yt65156_items: {item.item_no} "
                         f"as its  status is {item.item_status_en}")

    return yt65156_items, yt65217_items, items_without_iplan


class EditExportOrderMutation(BaseMutation):
    success = graphene.Boolean()
    iplan_messages = graphene.List(IPlanYT65156Message)
    sap_item_messages = graphene.List(SapItemMessage)
    sap_order_messages = graphene.List(SapOrderMessage)
    sap_warning_messages = graphene.List(WarningMessage)

    class Arguments:
        input = EditExportOrderInput(required=True)

    class Meta:
        description = "Edit export order"
        return_field_name = "order"
        error_type_field = "scgp_export_error"
        error_type_class = ScgpExportError

    @classmethod
    def perform_mutation(cls, root, info, **data):
        start_time = time.time()
        # -----Initial value----------------------#
        # ------Extract data from input--------#

        request_input = data.get("input")
        order_so_no = request_input.get("so_no")
        order_header_data = request_input.get("order_header")
        order_items_data = request_input.get("order_items", [])
        order_item__ids = list(map(lambda item: item.get("id"), order_items_data))
        dict_order_items_data = reduce(
            lambda prev, next: {next.id: next, **prev}, order_items_data, {}
        )
        sap_order_message = []
        sap_item_message = []
        logging.info(
            f"[Export change order] Order: {order_so_no} request payload from FE :{data}"
            f" by user: {info.context.user}"
        )

        # ------End of extract data from input--------#

        order = (
            Order.objects.annotate(
                sale_org_code=F("sales_organization__code"),
                sale_group_code=F("sales_group__code"),
                sold_to__sold_to_code=F("sold_to__sold_to_code"),
            )
            .filter(so_no=order_so_no)
            .first()
        )
        order_items = OrderLines.objects.filter(
            order=order, id__in=order_item__ids
        ).in_bulk(field_name="id")

        dict_order_items_by_item_no = reduce(
            lambda prev, next: {next.item_no: next, **prev}, order_items.values(), {}
        )
        # Currently disable this one since it's unfinished
        # validate_edit_order(
        #     order=order,
        #     order_items=order_items,
        #     input_data=order_header_data,
        #     order_item_input_data=dict_order_items_data,
        # )

        updated_order_header_data = None
        if order_header_data:
            updated_order_header_data = get_order_header_updated_data(
                order, order_header_data
            )
        logging.info(f"[Export change order] User updated order header fields:{updated_order_header_data}")

        (
            items_call_yt65156,
            items_call_yt65217,
            items_without_iplan,
        ) = get_items_by_item_status(order_items, dict_order_items_data)
        model_items_with_request_iplan = []
        rollback_items = set()
        iplan_success_items = []
        default_plant = ""
        for k, v in items_without_iplan.items():
            model_items_with_request_iplan.append(
                {
                    "item_no": v.item_no.lstrip("0"),
                    "iplan_item_no": None,
                    "db_item": v,
                    "item_input_data": dict_order_items_data.get(str(k)),
                    "iplan_item": None,
                    "update_flag": "U",
                }
            )

        if items_call_yt65156:
            logging.info("[Export change order] Calling iplan YT-65156")
            iplan_request, list_item_yt65156 = handle_yt65156_request(
                order=order,
                order_items_model=items_call_yt65156,
                order_items_updated_data=dict_order_items_data,
            )
            logging.info("[Export change order] Called iplan YT-65156")

            iplan_success_items = list_item_yt65156.get(
                IPlanResponseStatus.SUCCESS.value
            )

            for item in iplan_success_items:
                line_number = item.get("lineNumber")
                parse_line_number = str(int(float(line_number))) if line_number else ""
                if parse_line_number:
                    rollback_items.add(parse_line_number)

            # If IPlan is having failed items, end flow
            logging.info(f"[Export change order] Iplan YT-65156 errors {list_item_yt65156.get(IPlanResponseStatus.FAILURE.value)}")
            if len(
                    failed_items := list_item_yt65156.get(IPlanResponseStatus.FAILURE.value)
            ):
                if rollback_items:
                    logging.info("[Export change Order] calling..Iplan YT-65156 rollback")
                    handle_yt65156_rollback(order, rollback_items)
                    logging.info("[Export change Order] called Iplan YT-65156 rollback")
                logging.info(
                    f"[Export change order] Time Taken to complete FE request: {time.time() - start_time} seconds")
                return cls(
                    success=False,
                    iplan_messages=list(map(get_iplan_message, failed_items)),
                )

            max_item_no = max(
                [int(item.item_no or 0) for _id, item in order_items.items()],
                default=10,
            )

            for item in iplan_success_items:
                line_number = item.get("lineNumber")
                parse_line_number = str(int(float(line_number)))
                original_item_model = dict_order_items_by_item_no.get(parse_line_number)
                item_input_data = dict_order_items_data.get(str(original_item_model.id))
                if line_number == f"{parse_line_number}.001":
                    default_plant = item.get("warehouseCode")
                    model_items_with_request_iplan.append(
                        {
                            "item_no": parse_line_number,
                            "iplan_item_no": line_number,
                            "db_item": original_item_model,
                            "item_input_data": item_input_data,
                            "iplan_item": item,
                            "update_flag": "U",
                        }
                    )
                else:
                    max_item_no += 10
                    model_items_with_request_iplan.append(
                        {
                            "item_no": str(max_item_no),
                            "iplan_item_no": line_number,
                            "db_item": original_item_model,
                            "item_input_data": item_input_data,
                            "iplan_item": item,
                            "update_flag": "I",
                        }
                    )

        if items_call_yt65217:
            logging.info("[Export change order] Calling iplan YT-65217")
            _response, response_lines = handle_yt65217_update_order(
                order,
                items=items_call_yt65217.values(),
                order_lines_updated_data=dict_order_items_data,
            )
            logging.info(f"[Export change order] Called iplan YT-65217. Errors {response_lines.get(IPlanResponseStatus.FAILURE.value)}")

            if failed_yt65217_items := response_lines.get(
                    IPlanResponseStatus.FAILURE.value
            ):
                logging.info(
                    f"[Export change order] Time Taken to complete FE request: {time.time() - start_time} seconds")
                return cls(
                    success=False,
                    iplan_messages=list(map(get_yt65217_message, failed_yt65217_items)),
                    sap_order_messages=sap_order_message,
                    sap_item_messages=sap_item_message,
                )

            yt65217_success_item = response_lines.get(
                IPlanResponseStatus.SUCCESS.value, []
            )

            for item in yt65217_success_item:
                item_no = item.get("lineCode", "")
                original_item_model = dict_order_items_by_item_no.get(item_no, None)
                item_input_data = dict_order_items_data.get(str(original_item_model.id))
                model_items_with_request_iplan.append(
                    {
                        "item_no": item_no,
                        "iplan_item_no": item_no,
                        "db_item": original_item_model,
                        "item_input_data": item_input_data,
                        "iplan_item": None,
                        "update_flag": "U",
                        "from": "yt65217",
                    }
                )
        try:
            logging.info("[Export change order] calling.... ES21")
            (
                _response,
                messages,
                items_out,
                schedules_out,
                order_items_in,
                order_schedules_in,
            ) = request_es21_update_export_order(
                order=order,
                i_plan_request_items=model_items_with_request_iplan,
                order_header_data=order_header_data,
                updated_order_header_data=updated_order_header_data,
                default_plant=default_plant,
            )
            logging.info(f"[Export change order] called ES21. Failure items from ES21: {messages.get('fail','')}")
            (
                sap_order_message,
                sap_item_message,
                is_being_process,
                sap_success
            ) = get_error_messages_from_sap_response_for_change_order(_response)

            sap_warning_messages = get_sap_warning_messages(_response)
        except Exception as e:
            logging.info(f"[Export change order] Exception while updating order from  Es21: {e}")
            handle_yt65156_rollback(order, rollback_items)
            logging.info(
                f"[Export change order] Time Taken to complete FE request: {time.time() - start_time} seconds")
            raise e

        for v in model_items_with_request_iplan:
            schedule_out = list(
                filter(
                    lambda item, value=v: item.get("itemNo") == str(value.get("item_no", "")).zfill(6),
                    schedules_out or [],
                )
            )
            if schedule_out:
                v["item_schedule_out"] = schedule_out[0]

        error_messages = messages.get("fail", [])
        if error_messages:
            if items_call_yt65217:
                order_lines_fail = []
                if order_items_in:
                    for id, line in order_items.items():
                        if line.item_no in [item["itemNo"] for item in order_items_in] \
                                and validate_item_status_scenario2_3(line.item_status_en):
                            order_lines_fail.append(line)
                elif order_schedules_in:
                    for id, line in order_items.items():
                        if line.item_no in [item["itemNo"] for item in order_schedules_in] \
                                and validate_item_status_scenario2_3(line.item_status_en):
                            order_lines_fail.append(line)
                update_attention_type_r5(order_lines_fail)
            if rollback_items:
                handle_yt65156_rollback(order, rollback_items)
            logging.info(
                f"[Export change order] Time Taken to complete FE request: {time.time() - start_time} seconds")
            return cls(
                success=False,
                iplan_messages=[],
                sap_order_messages=sap_order_message,
                sap_item_messages=sap_item_message,
                sap_warning_messages=sap_warning_messages
            )
        failed_item_no = []
        iplan_messages=[]
        if iplan_success_items:
            items = list(
                filter(
                    lambda item: item.get("iplan_item", None),
                    model_items_with_request_iplan,
                )
            )
            _response, response_item = handle_yt65156_confirm(order, updated_order_header_data, items, schedules_out)
            if failed_confirm_items := response_item.get(IPlanResponseStatus.FAILURE.value, []):
                failed_item_no = list(map(lambda item: {"item_no": item.get("lineNumber")}, failed_confirm_items))
                iplan_messages = list(map(get_iplan_message, failed_confirm_items))
        update_order_after_request_mulesoft(
            order, order_header_data, model_items_with_request_iplan, failed_item_no, order_items.values()
        )
        logging.info(f"[Export change order] for the order: {request_input.get('so_no', '')}"
                     f" calling ES26 to sync data from SAP to EOR db")
        es26_response = call_sap_es26(
            so_no=request_input.get("so_no"),
            order_id=order.id,
        )
        sync_export_order_from_es26(es26_response)
        logging.info(f"[Export change order] Called ES26")
        logging.info(
            f"[Export change order] Time Taken to complete FE request: {time.time() - start_time} seconds")
        diff_time = time.time() - start_time
        for api_name in ["ES14", "ES15"]:
            force_update_attributes("function", api_name, {"orderId": order.id})
        add_metric_process_order(
            settings.NEW_RELIC_CHANGE_ORDER_METRIC_NAME,
            int(diff_time * 1000),
            start_time,
            "SaveOrder",
            order_type=OrderType.EXPORT,
            order_id=order.id
        )
        return cls(
            success=True, iplan_messages=iplan_messages or [], sap_order_messages=sap_order_message,
            sap_item_messages=sap_item_message, sap_warning_messages=sap_warning_messages
        )
