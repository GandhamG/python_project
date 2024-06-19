# from saleor.graphql.tests.utils import get_graphql_content
# from scgp_customer.models import CustomerOrderLine
# from scgp_customer.tests.operations import ADD_PRODUCTS_TO_CUSTOMER_ORDER


# def test_add_products_to_customer_order_successfully(
#     scgp_customer_user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
#     scgp_customer_product_variants,
#     scgp_customer_orders,
#     scgp_customer_order_lines,
# ):
#     current_total_lines = CustomerOrderLine.objects.filter(
#         order_id=scgp_customer_orders[0].id
#     ).count()
#     variables = {
#         "id": scgp_customer_orders[0].id,
#         "input": [
#             {
#                 "contractProductId": scgp_customer_contract_products[1].id,
#                 "variantId": scgp_customer_product_variants[4].id,
#                 "quantity": 12,
#             },
#             {
#                 "contractProductId": scgp_customer_contract_products[1].id,
#                 "variantId": scgp_customer_product_variants[5].id,
#                 "quantity": 10,
#             },
#         ],
#     }
#     scgp_customer_user_api_client.post_graphql(
#         ADD_PRODUCTS_TO_CUSTOMER_ORDER, variables
#     )

#     assert (
#         CustomerOrderLine.objects.filter(order_id=scgp_customer_orders[0].id).count()
#         == current_total_lines + 2
#     )


# def test_add_products_to_customer_order_with_quantity_smaller_than_zero(
#     scgp_customer_user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
#     scgp_customer_product_variants,
#     scgp_customer_orders,
#     scgp_customer_order_lines,
# ):
#     variables = {
#         "id": scgp_customer_orders[0].id,
#         "input": [
#             {
#                 "contractProductId": scgp_customer_contract_products[1].id,
#                 "variantId": scgp_customer_product_variants[4].id,
#                 "quantity": -12,
#             },
#             {
#                 "contractProductId": scgp_customer_contract_products[1].id,
#                 "variantId": scgp_customer_product_variants[5].id,
#                 "quantity": 10,
#             },
#         ],
#     }
#     response = scgp_customer_user_api_client.post_graphql(
#         ADD_PRODUCTS_TO_CUSTOMER_ORDER, variables
#     )
#     content = get_graphql_content(response)
#     error_string = "Value must be greater than 0. Unsupported value: -12.0"
#     assert (
#         content["data"]["addProductToCustomerOrder"]["errors"][0]["message"]
#         == error_string
#     )
