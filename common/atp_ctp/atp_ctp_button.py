from common.atp_ctp.enums import AtpCtpStatus
from scg_checkout.graphql.enums import IPlanOrderItemStatus
from scg_checkout.graphql.helper import update_order_status


def set_status_for_order_line(order_line):
    if order_line.iplan.order_type == AtpCtpStatus.ATP_ON_HAND.value:
        order_line.item_status_en = IPlanOrderItemStatus.FULL_COMMITTED_ORDER.value
    elif order_line.iplan.order_type == AtpCtpStatus.ATP_FUTURE.value:
        order_line.item_status_en = IPlanOrderItemStatus.PLANNING_OUTSOURCING.value
    else:
        order_line.item_status_en = IPlanOrderItemStatus.ITEM_CREATED.value

    order_line.item_status_th = (
        IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
            order_line.item_status_en
        )
    )
    order_line.item_status_en_rollback = None


def update_status_for_order(order):
    status_en, status_thai = update_order_status(order.id)
    order.status = status_en
    order.status_thai = status_thai
    order.save()


def update_field_item_no_latest_for_order(order_lines):
    if not order_lines:
        return

    order = order_lines[0].order
    item_no_latest = order.item_no_latest or 0

    item_no_latest = max(
        max(int(order_line.item_no) for order_line in order_lines),
        int(item_no_latest),
    )
    order.item_no_latest = str(item_no_latest)
    order.save()
