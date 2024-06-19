# from saleor.graphql.tests.utils import assert_graphql_error_with_message
# from scgp_customer.graphql.enums import ScgpCustomerOrderStatus
# from scgp_customer.models import CustomerOrder
# from scgp_customer.tests.operations import UPDATE_CUSTOMER_ORDER_MUTATION


# def test_update_customer_order_successfully(
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
#         "input": {
#             "orderDate": "2022-05-12",
#             "orderNo": "123212121",
#             "requestDeliveryDate": "2022-05-14",
#             "shipTo": "126 Phung Hung",
#             "billTo": "so 2 Tran Vy Mai Dich",
#             "unloadingPoint": "so 2 Tran Vy Mai Dich",
#             "remarkForInvoice": "some thing",
#             "internalCommentsToWarehouse": "test comment warehouse",
#             "confirm": True,
#         },
#     }
#     scgp_customer_user_api_client.post_graphql(
#         UPDATE_CUSTOMER_ORDER_MUTATION, variables
#     )
#     order = CustomerOrder.objects.get(id=scgp_customer_orders[0].id)
#     assert str(order.order_date) == variables.get("input").get("orderDate")
#     assert order.order_no == variables.get("input").get("orderNo")
#     assert str(order.request_delivery_date) == variables.get("input").get(
#         "requestDeliveryDate"
#     )
#     assert order.ship_to == variables.get("input").get("shipTo")
#     assert order.bill_to == variables.get("input").get("billTo")
#     assert order.unloading_point == variables.get("input").get("unloadingPoint")
#     assert order.remark_for_invoice == variables.get("input").get("remarkForInvoice")
#     assert order.remark_for_logistic == variables.get("input").get("remarkForLogistic")
#     assert order.internal_comments_to_warehouse == variables.get("input").get(
#         "internalCommentsToWarehouse"
#     )
#     assert order.status == ScgpCustomerOrderStatus.CONFIRMED.value


# def test_update_customer_order_with_confirmed_order(
#     scgp_customer_user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
#     scgp_customer_product_variants,
#     scgp_customer_orders,
#     scgp_customer_order_lines,
# ):
#     variables = {
#         "id": scgp_customer_orders[1].id,
#         "input": {
#             "orderDate": "2022-05-12",
#             "orderNo": "123212121",
#             "requestDeliveryDate": "2022-05-14",
#             "shipTo": "126 Phung Hung",
#             "billTo": "so 2 Tran Vy Mai Dich",
#             "unloadingPoint": "so 2 Tran Vy Mai Dich",
#             "remarkForInvoice": "some thing",
#         },
#     }
#     response = scgp_customer_user_api_client.post_graphql(
#         UPDATE_CUSTOMER_ORDER_MUTATION, variables
#     )
#     error_string = "Confirmed order can not change status!"
#     assert_graphql_error_with_message(response, error_string)


# def test_update_customer_order_with_wrong_order_id(
#     scgp_customer_user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
#     scgp_customer_product_variants,
#     scgp_customer_orders,
#     scgp_customer_order_lines,
# ):
#     order_id = 9999
#     variables = {
#         "id": order_id,
#         "input": {
#             "orderDate": "2022-05-12",
#             "orderNo": "123212121",
#             "requestDeliveryDate": "2022-05-14",
#             "shipTo": "126 Phung Hung",
#             "billTo": "so 2 Tran Vy Mai Dich",
#             "unloadingPoint": "so 2 Tran Vy Mai Dich",
#             "remarkForInvoice": "some thing",
#         },
#     }
#     response = scgp_customer_user_api_client.post_graphql(
#         UPDATE_CUSTOMER_ORDER_MUTATION, variables
#     )
#     error_string = "CustomerOrder matching query does not exist."
#     assert_graphql_error_with_message(response, error_string)


# def test_update_customer_order_with_others_order(
#     scgp_customer_user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
#     scgp_customer_product_variants,
#     scgp_customer_orders,
#     scgp_customer_order_lines,
# ):
#     variables = {
#         "id": scgp_customer_orders[2].id,
#         "input": {
#             "orderDate": "2022-05-12",
#             "orderNo": "123212121",
#             "requestDeliveryDate": "2022-05-14",
#             "shipTo": "126 Phung Hung",
#             "billTo": "so 2 Tran Vy Mai Dich",
#             "unloadingPoint": "so 2 Tran Vy Mai Dich",
#             "remarkForInvoice": "some thing",
#         },
#     }
#     response = scgp_customer_user_api_client.post_graphql(
#         UPDATE_CUSTOMER_ORDER_MUTATION, variables
#     )
#     error_string = "Can not update other's order!"
#     assert_graphql_error_with_message(response, error_string)
