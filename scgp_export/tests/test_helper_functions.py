from common.enum import ChangeOrderAPIFlow
from sap_migration.models import OrderLineIPlan, OrderLines
from scg_checkout.graphql.enums import ProductionStatus
from scgp_export.graphql.mutations.edit_order import get_item_api_flow


def test_api_flow_function():
    order_line = OrderLines()
    order_line.iplan = OrderLineIPlan()
    # Case ATP
    order_line.iplan.order_type = "ATP OnHand"
    assert get_item_api_flow(order_line) == ChangeOrderAPIFlow.YT65156

    # Case CTP
    order_line.iplan.order_type = "CTP"

    # No production status
    order_line.production_status = None
    assert get_item_api_flow(order_line) == ChangeOrderAPIFlow.YT65156

    # Production status belong to scenario 1
    production_status_for_scenario_1 = [
        ProductionStatus.UNALLOCATED.value,
        ProductionStatus.ALLOCATED.value,
        ProductionStatus.CONFIRMED.value,
    ]

    for status in production_status_for_scenario_1:
        order_line.production_status = status
        assert get_item_api_flow(order_line) == ChangeOrderAPIFlow.YT65156

    production_status_for_scenario_2_3 = [
        ProductionStatus.CLOSE_RUN.value,
        ProductionStatus.TRIMMED.value,
        ProductionStatus.IN_PRODUCTION.value,
        ProductionStatus.COMPLETED.value,
    ]

    for status in production_status_for_scenario_2_3:
        order_line.production_status = status
        assert get_item_api_flow(order_line) == ChangeOrderAPIFlow.YT65217
