
from scg_checkout.graphql.validators import check_object_field_in_range

def validate_delivery_tolerance(order_lines: list):
    for order_line in order_lines:
        delivery_tolerance = order_line.get("delivery_tolerance", {})
        check_object_field_in_range(delivery_tolerance, "over", 0, 100)
        check_object_field_in_range(delivery_tolerance, "under", 0, 100)


