# from saleor.graphql.tests.utils import (
#     assert_graphql_error_with_message,
#     get_graphql_content,
# )
# from scgp_customer.tests.operations import CREATE_DRAFT_ORDER_MUTATION


# def test_create_draft_order_success(
#     user_api_client,
#     scgp_customer_contracts,
#     scgp_sold_to_for_search,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contract_product,
# ):
#     variables = {
#         "input": {
#             "orderInformation": {"contractId": scgp_customer_contracts[1].id},
#             "lines": [
#                 {
#                     "contractProductId": scgp_customer_contract_product[1].id,
#                     "variantId": scgp_customer_product_variants[1].id,
#                     "quantity": 15,
#                 },
#                 {
#                     "contractProductId": scgp_customer_contract_product[2].id,
#                     "variantId": scgp_customer_product_variants[3].id,
#                     "quantity": 10,
#                 },
#             ],
#         }
#     }
#     response = user_api_client.post_graphql(CREATE_DRAFT_ORDER_MUTATION, variables)
#     content = get_graphql_content(response)
#     order = content["data"]["createCustomerOrder"]["order"]
#     errors = content["data"]["createCustomerOrder"]["errors"]

#     assert len(errors) == 0
#     assert order["contract"]["id"] == str(scgp_customer_contracts[1].id)
#     assert order["contract"]["code"] == str(scgp_customer_contracts[1].code).zfill(10)
#     assert order["contract"]["projectName"] == scgp_customer_contracts[1].project_name

#     assert len(order["lines"]) == 2
#     assert order["lines"][1]["contractProduct"]["id"] == str(
#         scgp_customer_contract_product[2].id
#     )
#     assert (
#         order["lines"][1]["contractProduct"]["product"]["name"]
#         == scgp_customer_contract_product[2].product.name
#     )
#     assert order["lines"][1]["variant"]["id"] == str(
#         scgp_customer_product_variants[3].id
#     )
#     assert order["lines"][1]["variant"]["product"]["id"] == str(
#         order["lines"][1]["contractProduct"]["product"]["id"]
#     )

#     assert order["lines"][0]["totalPrice"] == round(
#         scgp_customer_contract_product[1].price_per_unit * order["lines"][0]["quantity"]
#     )
#     assert order["totalPrice"] == round(
#         scgp_customer_contract_product[1].price_per_unit * order["lines"][0]["quantity"]
#         + scgp_customer_contract_product[2].price_per_unit
#         * order["lines"][1]["quantity"]
#     )


# def test_create_draft_order_error_contract_not_exist(
#     user_api_client,
#     scgp_customer_contracts,
#     scgp_sold_to_for_search,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contract_product,
# ):
#     variables = {
#         "input": {
#             "orderInformation": {"contractId": 999999},
#             "lines": [
#                 {
#                     "contractProductId": scgp_customer_contract_product[1].id,
#                     "variantId": scgp_customer_product_variants[1].id,
#                     "quantity": 10,
#                 },
#                 {
#                     "contractProductId": scgp_customer_contract_product[2].id,
#                     "variantId": scgp_customer_product_variants[3].id,
#                     "quantity": 15,
#                 },
#             ],
#         }
#     }
#     response = user_api_client.post_graphql(CREATE_DRAFT_ORDER_MUTATION, variables)
#     message = "CustomerContract matching query does not exist."
#     assert_graphql_error_with_message(response, message)


# def test_create_draft_order_error_contract_product_not_exist(
#     user_api_client,
#     scgp_customer_contracts,
#     scgp_sold_to_for_search,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contract_product,
# ):
#     variables = {
#         "input": {
#             "orderInformation": {"contractId": scgp_customer_contracts[1].id},
#             "lines": [
#                 {
#                     "contractProductId": 999999,
#                     "variantId": scgp_customer_product_variants[1].id,
#                     "quantity": 10,
#                 },
#             ],
#         }
#     }
#     response = user_api_client.post_graphql(CREATE_DRAFT_ORDER_MUTATION, variables)
#     message = "CustomerContractProduct matching query does not exist."
#     assert_graphql_error_with_message(response, message)


# def test_create_draft_order_error_variant_not_exist(
#     user_api_client,
#     scgp_customer_contracts,
#     scgp_sold_to_for_search,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contract_product,
# ):
#     variables = {
#         "input": {
#             "orderInformation": {"contractId": scgp_customer_contracts[1].id},
#             "lines": [
#                 {
#                     "contractProductId": scgp_customer_contract_product[1].id,
#                     "variantId": 99999,
#                     "quantity": 10,
#                 },
#             ],
#         }
#     }
#     response = user_api_client.post_graphql(CREATE_DRAFT_ORDER_MUTATION, variables)
#     message = "CustomerProductVariant matching query does not exist."
#     assert_graphql_error_with_message(response, message)


# def test_create_draft_order_error_zero_quantity(
#     user_api_client,
#     scgp_customer_contracts,
#     scgp_sold_to_for_search,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contract_product,
# ):
#     variables = {
#         "input": {
#             "orderInformation": {"contractId": scgp_customer_contracts[1].id},
#             "lines": [
#                 {
#                     "contractProductId": scgp_customer_contract_product[1].id,
#                     "variantId": scgp_customer_product_variants[1].id,
#                     "quantity": 0,
#                 },
#                 {
#                     "contractProductId": scgp_customer_contract_product[2].id,
#                     "variantId": scgp_customer_product_variants[3].id,
#                     "quantity": -10,
#                 },
#             ],
#         }
#     }
#     response = user_api_client.post_graphql(CREATE_DRAFT_ORDER_MUTATION, variables)
#     content = get_graphql_content(response)
#     order = content["data"]["createCustomerOrder"]["order"]
#     errors = content["data"]["createCustomerOrder"]["errors"]

#     assert order is None
#     assert errors[0]["message"] == "quantity must be greater than 0"
