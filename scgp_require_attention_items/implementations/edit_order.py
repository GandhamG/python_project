import logging

from sap_migration import models as sap_migration_models
from scg_checkout.graphql.enums import (
    IPlanUpdateItemTime,
    ReasonForChangeRequestDateEnum,
    SapUpdateFlag,
)
from scgp_require_attention_items.graphql.helper import update_attention_type_r1
from scgp_require_attention_items.implementations.edit_order_breakdown import (
    call_i_plan_update_order,
    check_recall_i_plan,
    recall_i_plan_atp_ctp,
    update_remark_order_line,
)


def request_api_change_order(
    order,
    manager,
    origin_order_lines,
    updated_order_lines,
    accept_confirm_date=False,
    call_type=None,
    sap_update_flag=None,
    original_order=None,
    updated_data=None,
    pre_update_lines=None,
    export_delete_flag=True,
    only_update=False,
    require_attention=False,
):
    """
    Call i-plan and SAP to update order
    If call SAP error then rollback order
    If call i-plan error then update required attention is R5
    @param order:
    @param manager:
    @param origin_order_lines: order line before update
    @param updated_order_lines: order line after updated
    @param call_type: use for send mail from eo upload feature.
    @param sap_update_flag:
    @param original_order:
    @return:
    """
    # mark order line change request date
    pre_update_lines = pre_update_lines or {}
    mapping_origin_order_line = {}
    for order_line in origin_order_lines:
        mapping_origin_order_line[str(order_line.item_no)] = order_line
    order_lines_change_request_date = {}
    order_lines_update_remark = []
    for order_line in updated_order_lines:
        if (
            str(order_line.item_no) in mapping_origin_order_line
            and mapping_origin_order_line[str(order_line.item_no)].request_date
            != order_line.request_date
        ):
            order_lines_change_request_date[
                order_line.item_no
            ] = order_line.request_date_change_reason

            # stamp remark C3 C4 for order line
            remark = (
                "C4"
                if order_line.request_date_change_reason
                == ReasonForChangeRequestDateEnum.C4.value
                else "C3"
            )
            order_line.remark = update_remark_order_line(order_line.remark, remark)
            order_lines_update_remark.append(order_line)

    # update remark C3 C4 for order line when change order line request date
    sap_migration_models.OrderLines.objects.bulk_update(
        order_lines_update_remark, ["remark"]
    )
    # Validation order data after change
    success = True
    sap_order_messages = []
    sap_item_messages = []
    i_plan_messages = []
    logging.info(f"For Order id: {order.id},calling check_recall_i_plan method")
    result = check_recall_i_plan(
        order,
        origin_order_lines,
        updated_order_lines,
        sap_update_flag,
        accept_confirm_date,
    )
    i_plan_update_items = result.get("i_plan_update_items")
    new_items = result.get("new_items", [])
    delete_items = result.get("delete_items", [])

    # Call ES27 to update order item which are changed quantity, plant, request date
    if len(
        update_items := i_plan_update_items.get(
            IPlanUpdateItemTime.BEFORE_PRODUCTION.value
        )
    ):
        # Set flag for update item
        update_items_flag = {}
        for item in update_items:
            update_items_flag[str(item.item_no)] = SapUpdateFlag.UPDATE.value

        # Call i-plan to get new solution
        # and call SAP to update order
        logging.info(f"For Order id: {order.id},Calling recall_i_plan_atp_ctp method")
        response = recall_i_plan_atp_ctp(
            order,
            update_items,
            manager,
            accept_confirm_date,
            call_type=call_type,
            sap_update_flag=update_items_flag,
            original_order=original_order,
            original_order_lines=origin_order_lines,
            pre_update_lines=pre_update_lines,
            export_delete_flag=export_delete_flag,
            updated_items=update_items,
            require_attention=require_attention,
        )
        if not response.get("success"):
            success = False
        sap_order_messages += response.get("sap_order_messages")
        sap_item_messages += response.get("sap_item_messages")
        i_plan_messages += response.get("i_plan_messages")
    else:
        if len(
            update_items := i_plan_update_items.get(
                IPlanUpdateItemTime.DURING_PRODUCTION.value
            )
        ):
            logging.info(
                f"For Order id: {order.id},calling call_i_plan_update_order method"
            )
            call_i_plan_update_order(order, update_items, manager, call_type=call_type)
            # Update attention for items that have changed request_date before confirmed_date
            update_attention_r1_items = result.get("update_attention_r1_items")
            if update_attention_r1_items and len(update_attention_r1_items):
                update_attention_type_r1(update_attention_r1_items)

        if len(
            update_items := i_plan_update_items.get(
                IPlanUpdateItemTime.AFTER_PRODUCTION.value
            )
        ):
            # Call SAP to update order
            # and call i-plan after SAP success
            # Call ES21 to update order items which are inserted or aren't changed plant, quantity, request date
            logging.info(
                f"For Order id: {order.id},calling call_i_plan_update_order method"
            )
            call_i_plan_update_order(order, update_items, manager, call_type=call_type)
    es21_items_flag = {}
    for new_item in new_items:
        es21_items_flag[str(new_item.item_no)] = SapUpdateFlag.INSERT.value
    for delete_item in delete_items:
        es21_items_flag[str(delete_item.item_no)] = SapUpdateFlag.DELETE.value

    return {
        "success": success,
        "sap_order_messages": sap_order_messages,
        "sap_item_messages": sap_item_messages,
        "i_plan_messages": i_plan_messages,
    }
