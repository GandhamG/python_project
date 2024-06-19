from sap_migration.models import OrderLineIPlan, OrderLines
from scg_checkout.graphql.enums import IPlanOrderItemStatus
from scg_checkout.graphql.resolves.orders import resolve_allow_change_inquiry_method


def test_resolve_allow_change_inquiry_method():
    order_line = OrderLines()
    order_line.iplan = OrderLineIPlan()
    # CTP case
    # expect allow change with scenario 1
    order_line.iplan.atp_ctp = "CTP"
    order_line.item_status_en = "Item Created"
    assert resolve_allow_change_inquiry_method(order_line)
    order_line.production_status = None
    assert resolve_allow_change_inquiry_method(order_line)
    production_status = ["Unallocated", "Allocated", "Confirmed"]
    for status in production_status:
        order_line.production_status = status
        assert resolve_allow_change_inquiry_method(order_line)

    # expect NOT allow change with scenario 2, scenario 3
    order_line.item_status_en = None
    production_status = [
        # scenario 2
        "Closed Run",
        "Trimmed",
        "In Production",
        # scenario 3
        "Completed",
    ]
    for status in production_status:
        order_line.production_status = status
        assert not resolve_allow_change_inquiry_method(order_line)

    # Case ATP
    order_line.iplan.atp_ctp = "ATP"
    # No item status
    order_line.item_status_en = None
    assert resolve_allow_change_inquiry_method(order_line)

    disabled_inquiry_method = [
        IPlanOrderItemStatus.PARTIAL_DELIVERY.value,
        IPlanOrderItemStatus.COMPLETE_DELIVERY.value,
        IPlanOrderItemStatus.CANCEL.value,
    ]
    for scenario in disabled_inquiry_method:
        order_line.item_status_en = scenario
        assert not resolve_allow_change_inquiry_method(order_line)
