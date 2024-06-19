# from saleor.graphql.tests.utils import get_graphql_content
# from scgp_customer.models import CustomerOrder, CustomerOrderLine
# from scgp_customer.tests.operations import CUSTOMER_ORDER_QUERY


# def test_get_customer_order_with_correct_id(
#     user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
#     scgp_customer_product_variants,
#     scgp_customer_orders,
#     scgp_customer_order_lines,
# ):
#     variables = {"orderId": scgp_customer_orders[0].id, "first": 2}
#     response = user_api_client.post_graphql(CUSTOMER_ORDER_QUERY, variables)
#     content = get_graphql_content(response)
#     result_order = content["data"]["customerOrder"]
#     order = CustomerOrder.objects.get(id=scgp_customer_orders[0].id)
#     total_order_line = CustomerOrderLine.objects.filter(
#         order_id=scgp_customer_orders[0].id
#     ).count()
#     assert result_order.get("id") == str(order.id)
#     assert result_order.get("contract").get("id") == str(order.contract.id)
#     assert result_order.get("totalPrice") == order.total_price
#     assert result_order.get("totalPriceIncTax") == order.total_price_inc_tax
#     assert result_order.get("taxAmount") == order.tax_amount
#     assert len(result_order.get("lines")) == total_order_line


# def test_get_customer_order_with_incorrect_id(
#     user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
#     scgp_customer_product_variants,
#     scgp_customer_orders,
#     scgp_customer_order_lines,
# ):
#     variables = {"orderId": "10000", "first": 2}
#     response = user_api_client.post_graphql(CUSTOMER_ORDER_QUERY, variables)
#     content = get_graphql_content(response)
#     assert content["data"]["customerOrder"] is None
