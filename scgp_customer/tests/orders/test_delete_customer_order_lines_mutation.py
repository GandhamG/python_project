# from scgp_customer.models import CustomerOrderLine
# from scgp_customer.tests.operations import DELETE_CUSTOMER_ORDER_LINES


# def test_delete_customer_order_lines_with_ids(
#     scgp_customer_user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
#     scgp_customer_product_variants,
#     scgp_customer_orders,
#     scgp_customer_order_lines,
# ):
#     variables = {
#         "ids": [scgp_customer_order_lines[0].id, scgp_customer_order_lines[1].id],
#         "deleteAll": False,
#         "orderId": 5,
#     }
#     scgp_customer_user_api_client.post_graphql(DELETE_CUSTOMER_ORDER_LINES, variables)
#     assert (
#         CustomerOrderLine.objects.filter(
#             id__in=[scgp_customer_order_lines[0].id, scgp_customer_order_lines[1].id]
#         ).count()
#         == 0
#     )


# def test_delete_customer_order_lines_all_lines(
#     scgp_customer_user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
#     scgp_customer_product_variants,
#     scgp_customer_orders,
#     scgp_customer_order_lines,
# ):
#     variables = {"ids": [], "deleteAll": True, "orderId": scgp_customer_orders[0].id}
#     scgp_customer_user_api_client.post_graphql(DELETE_CUSTOMER_ORDER_LINES, variables)
#     assert (
#         CustomerOrderLine.objects.filter(order_id=scgp_customer_orders[0].id).count()
#         == 0
#     )
