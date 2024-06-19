from saleor.graphql.tests.utils import get_graphql_content

# from scgp_customer.models import CustomerOrderLine
from scgp_customer.tests.operations import UPDATE_CUSTOMER_ORDER_LINES_MUTATION

# def test_update_customer_order_lines_successful(
#     scgp_customer_user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
#     scgp_customer_product_variants,
#     scgp_customer_orders,
#     scgp_customer_order_lines,
# ):
#     variables = {
#         "orderId": scgp_customer_orders[0].id,
#         "input": {
#             "lines": [
#                 {
#                     "id": scgp_customer_order_lines[0].id,
#                     "quantity": 12,
#                     "requestDeliveryDate": "2022-05-04",
#                 },
#                 {
#                     "id": scgp_customer_order_lines[1].id,
#                     "quantity": 13,
#                     "requestDeliveryDate": "2022-05-03",
#                 },
#             ],
#         },
#     }
#     scgp_customer_user_api_client.post_graphql(
#         UPDATE_CUSTOMER_ORDER_LINES_MUTATION, variables
#     )
#     first_order_line = CustomerOrderLine.objects.get(id=scgp_customer_order_lines[0].id)
#     assert first_order_line.quantity == variables.get("input").get("lines")[0].get(
#         "quantity"
#     )
#     assert str(first_order_line.request_delivery_date) == variables.get("input").get(
#         "lines"
#     )[0].get("requestDeliveryDate")
#     second_order_line = CustomerOrderLine.objects.get(
#         id=scgp_customer_order_lines[1].id
#     )
#     assert second_order_line.quantity == variables.get("input").get("lines")[1].get(
#         "quantity"
#     )
#     assert str(second_order_line.request_delivery_date) == variables.get("input").get(
#         "lines"
#     )[1].get("requestDeliveryDate")


# def test_update_customer_order_lines_with_apply_all(
#     scgp_customer_user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
#     scgp_customer_product_variants,
#     scgp_customer_orders,
#     scgp_customer_order_lines,
# ):
#     request_delivery_date = "2022-06-11"
#     variables = {
#         "orderId": scgp_customer_orders[0].id,
#         "input": {"requestDeliveryDate": request_delivery_date, "applyAll": True},
#     }
#     scgp_customer_user_api_client.post_graphql(
#         UPDATE_CUSTOMER_ORDER_LINES_MUTATION, variables
#     )
#     changed_date_order_lines = CustomerOrderLine.objects.filter(
#         order_id=scgp_customer_orders[0].id, request_delivery_date=request_delivery_date
#     ).count()
#     total_order_lines = CustomerOrderLine.objects.filter(
#         order_id=scgp_customer_orders[0].id
#     ).count()
#     assert changed_date_order_lines == total_order_lines


def test_update_customer_order_lines_with_quantity_smaller_than_zero(
    scgp_customer_user_api_client,
    customers_for_search,
    scgp_customer_contracts,
    scgp_customer_contract_products,
    scgp_customer_product_variants,
    scgp_customer_orders,
    scgp_customer_order_lines,
):
    variables = {
        "orderId": scgp_customer_orders[0].id,
        "input": {
            "lines": [
                {
                    "id": scgp_customer_order_lines[0].id,
                    "quantity": -12,
                    "requestDeliveryDate": "2022-05-04",
                },
                {
                    "id": scgp_customer_order_lines[1].id,
                    "quantity": 13,
                    "requestDeliveryDate": "2022-05-03",
                },
            ],
        },
    }
    response = scgp_customer_user_api_client.post_graphql(
        UPDATE_CUSTOMER_ORDER_LINES_MUTATION, variables
    )
    content = get_graphql_content(response)
    error_string = "Value must be greater than 0. Unsupported value: -12.0"
    assert (
        content["data"]["updateCustomerOrderLines"]["errors"][0]["message"]
        == error_string
    )
