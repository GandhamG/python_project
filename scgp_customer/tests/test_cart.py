# import mock
# import pytest

# from saleor.account.models import User
from saleor.graphql.tests.utils import (
    assert_graphql_error_with_message,
    get_graphql_content,
    get_graphql_content_from_response,
)

# from scgp_customer.graphql.validators import validate_positive_decimal
# from scgp_customer.implementations.carts import customer_create_cart
# from scgp_customer.models import CustomerCart, CustomerCartItem, CustomerContractProduct
from scgp_customer.tests.operations import (  # CUSTOMER_CART_QUERY,; CUSTOMER_CART_TOTALS_QUERY,; CUSTOMER_CARTS_QUERY,; CUSTOMER_CONTRACT_PRODUCT_QUERY,
    CREATE_CUSTOMER_CART,
    DELETE_CUSTOMER_CART_ITEMS_MUTATION,
    UPDATE_CUSTOMER_CART_MUTATIONS,
)

# def test_create_customer_cart_success(
#     staff_api_client,
#     scgp_sold_to_for_search,
#     customers_for_search,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
# ):
#     create_by = User.objects.filter(email="staff_test@example.com").first()
#     variables = {
#         "input": {
#             "customerId": create_by.id,
#             "customerContractId": scgp_customer_contracts[0].id,
#             "lines": [
#                 {
#                     "productId": scgp_customer_products_for_search[0].id,
#                     "quantity": 10,
#                     "variantId": scgp_customer_product_variants[0].id,
#                 },
#                 {
#                     "productId": scgp_customer_products_for_search[0].id,
#                     "quantity": 10,
#                     "variantId": scgp_customer_product_variants[1].id,
#                 },
#             ],
#         }
#     }
#     response = staff_api_client.post_graphql(
#         CREATE_CUSTOMER_CART,
#         variables,
#     )

#     content = get_graphql_content(response)
#     cart_id = content["data"]["createCustomerCart"]["cart"].get("id")
#     cart_item = content["data"]["createCustomerCart"]["cart"]["cartItems"]
#     customer_cart = CustomerCart.objects.get(id=cart_id)
#     customer_cart_item = CustomerCartItem.objects.filter(cart_id=cart_id).count()
#     assert cart_id == str(customer_cart.id)
#     assert customer_cart_item == len(cart_item)


# def test_create_customer_cart_unacceptable_quantity(
#     staff_api_client,
#     scgp_sold_to_for_search,
#     customers_for_search,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
# ):
#     create_by = User.objects.filter(email="staff_test@example.com").first()
#     variables = {
#         "input": {
#             "customerId": create_by.id,
#             "customerContractId": scgp_customer_contracts[0].id,
#             "lines": [
#                 {
#                     "productId": scgp_customer_products_for_search[0].id,
#                     "quantity": 0.0,
#                     "variantId": scgp_customer_product_variants[0].id,
#                 },
#                 {
#                     "productId": scgp_customer_products_for_search[0].id,
#                     "quantity": 10,
#                     "variantId": scgp_customer_product_variants[1].id,
#                 },
#             ],
#         }
#     }
#     response = staff_api_client.post_graphql(
#         CREATE_CUSTOMER_CART,
#         variables,
#     )
#     quantity = variables["input"]["lines"][0]["quantity"]
#     message = f"Value must be greater than 0. Unsupported value: {quantity}"
#     content = get_graphql_content(response)
#     assert message == content["data"]["createCustomerCart"]["errors"][0]["message"]


# def test_create_customer_cart_over_remaining_quantity(
#     staff_api_client,
#     scgp_sold_to_for_search,
#     customers_for_search,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
# ):
#     create_by = User.objects.filter(email="staff_test@example.com").first()
#     variables = {
#         "input": {
#             "customerId": create_by.id,
#             "customerContractId": scgp_customer_contracts[0].id,
#             "lines": [
#                 {
#                     "productId": scgp_customer_products_for_search[0].id,
#                     "quantity": 10000000,
#                     "variantId": scgp_customer_product_variants[0].id,
#                 },
#                 {
#                     "productId": scgp_customer_products_for_search[0].id,
#                     "quantity": 10,
#                     "variantId": scgp_customer_product_variants[1].id,
#                 },
#             ],
#         }
#     }
#     response = staff_api_client.post_graphql(
#         CREATE_CUSTOMER_CART,
#         variables,
#     )
#     message = "Quantity can not over remaining"
#     assert_graphql_error_with_message(response, message)


# def test_create_customer_cart_invalid_quantity_type(
#     staff_api_client,
#     scgp_sold_to_for_search,
#     customers_for_search,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
# ):
#     create_by = User.objects.filter(email="staff_test@example.com").first()
#     variables = {
#         "input": {
#             "customerId": create_by.id,
#             "customerContractId": scgp_customer_contracts[0].id,
#             "lines": [
#                 {
#                     "productId": scgp_customer_products_for_search[0].id,
#                     "quantity": -11.65,
#                     "variantId": scgp_customer_product_variants[0].id,
#                 },
#                 {
#                     "productId": scgp_customer_products_for_search[0].id,
#                     "quantity": 10,
#                     "variantId": scgp_customer_product_variants[1].id,
#                 },
#             ],
#         }
#     }
#     response = staff_api_client.post_graphql(
#         CREATE_CUSTOMER_CART,
#         variables,
#     )
#     quantity = variables["input"]["lines"][0].get("quantity")
#     message = f"Value must be greater than 0. Unsupported value: {quantity}"
#     content = get_graphql_content(response)
#     assert message == content["data"]["createCustomerCart"]["errors"][0]["message"]


def test_create_customer_cart_missing_field_required(
    staff_api_client,
    scgp_sold_to_for_search,
    customers_for_search,
    scgp_customer_products_for_search,
    scgp_customer_product_variants,
    scgp_customer_contracts,
    scgp_customer_contract_products,
):
    variables = {
        "input": {
            "customerId": customers_for_search[0].id,
            "lines": [
                {
                    "productId": scgp_customer_products_for_search[0].id,
                    "quantity": 10,
                    "variantId": scgp_customer_product_variants[0].id,
                },
                {
                    "productId": scgp_customer_products_for_search[0].id,
                    "quantity": 10,
                    "variantId": scgp_customer_product_variants[1].id,
                },
            ],
        }
    }
    response = staff_api_client.post_graphql(
        CREATE_CUSTOMER_CART,
        variables,
    )
    message = 'field "customerContractId": Expected "ID!", found null.'
    assert_graphql_error_with_message(response, message)


# @mock.patch("scgp_customer.implementations.carts.create_or_update_customer_cart_items")
# def test_customer_create_cart_new_cart(
#     mock_cart_lines,
#     staff_api_client,
#     scgp_sold_to_for_search,
#     customers_for_search,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contracts,
#     scgp_customer_contract_products,
# ):
#     cart_lines = [
#         {
#             "product_id": scgp_customer_products_for_search[0].id,
#             "quantity": 10,
#             "variant_id": scgp_customer_product_variants[0].id,
#         }
#     ]

#     create_by = User.objects.filter(email="staff_test@example.com").first()
#     params = {
#         "customer_contract_id": scgp_customer_contracts[1].id,
#         "customer_id": create_by.id,
#         "lines": cart_lines,
#     }
#     cart = customer_create_cart(params, create_by)

#     mock_cart_lines.assert_called_once_with(
#         cart_lines, cart.id, scgp_customer_contracts[1].id
#     )
#     new_cart = CustomerCart.objects.last()
#     assert cart.id == new_cart.id


# def test_cart_query_validate_positive_decimal_success():
#     quantity = "10.5"
#     assert validate_positive_decimal(quantity) == quantity
#     assert validate_positive_decimal(float(quantity)) == float(quantity)


# def test_contract_query_validate_positive_decimal_invalid_value():
#     quantity = "-10.5"
#     message = f"Value must be greater than 0. Unsupported value: {quantity}"
#     with pytest.raises(Exception) as e:
#         validate_positive_decimal(quantity)
#     assert message == str(e.value.args[0])


# def test_customer_contract_product_query(
#     staff_api_client,
#     scgp_customer_contracts,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contract_products,
# ):
#     variables = {
#         "contractId": scgp_customer_contracts[0].id,
#         "productId": scgp_customer_products_for_search[0].id,
#     }
#     response = staff_api_client.post_graphql(CUSTOMER_CONTRACT_PRODUCT_QUERY, variables)
#     content = get_graphql_content(response)
#     customer_contract_product = CustomerContractProduct.objects.filter(
#         contract_id=variables["contractId"], product_id=variables["productId"]
#     ).first()
#     assert (
#         content["data"]["customerContractProduct"]["product"]["name"]
#         == customer_contract_product.product.name
#     )


# def test_customer_contract_product_query_not_exist_contract_id(
#     staff_api_client,
#     scgp_customer_contracts,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contract_products,
# ):
#     variables = {
#         "contractId": 2000,
#         "productId": scgp_customer_products_for_search[0].id,
#     }
#     response = staff_api_client.post_graphql(CUSTOMER_CONTRACT_PRODUCT_QUERY, variables)
#     content = get_graphql_content(response)

#     customer_contract_product_none = CustomerContractProduct.objects.filter(
#         contract_id=variables["contractId"]
#     ).first()
#     assert content["data"]["customerContractProduct"] == customer_contract_product_none


# def test_customer_contract_product_query_invalid_type(
#     staff_api_client,
#     scgp_customer_contracts,
#     scgp_customer_products_for_search,
#     scgp_customer_product_variants,
#     scgp_customer_contract_products,
# ):
#     variables = {
#         "contractId": "abc",
#         "productId": scgp_customer_products_for_search[0].id,
#     }
#     response = staff_api_client.post_graphql(CUSTOMER_CONTRACT_PRODUCT_QUERY, variables)
#     message = "Field 'id' expected a number but got 'abc'."
#     assert_graphql_error_with_message(response, message)


# def test_customer_carts(
#     scgp_customer_api_client, scgp_customer_carts, scgp_customer_cart_items
# ):
#     variables = {
#         "first": 10,
#     }

#     response = scgp_customer_api_client.post_graphql(CUSTOMER_CARTS_QUERY, variables)

#     content = get_graphql_content(response)
#     customer_carts = content["data"]["customerCarts"]["edges"]

#     assert customer_carts[0]["node"]["contract"]["code"] == "0000000002"
#     assert customer_carts[0]["node"]["contract"]["projectName"] == "P1"
#     assert customer_carts[0]["node"]["quantity"] == 3

#     assert customer_carts[1]["node"]["contract"]["code"] == "0000000001"
#     assert customer_carts[1]["node"]["contract"]["projectName"] == "P0"
#     assert customer_carts[1]["node"]["quantity"] == 3


# def test_customer_cart(
#     scgp_customer_api_client, scgp_customer_carts, scgp_customer_cart_items
# ):
#     variables = {"cartId": scgp_customer_carts[0].id}

#     response = scgp_customer_api_client.post_graphql(CUSTOMER_CART_QUERY, variables)
#     content = get_graphql_content(response)
#     customer_cart = content["data"]["customerCart"]

#     assert customer_cart["quantity"] == 3
#     assert customer_cart["cartItems"][0]["quantity"] == 100
#     assert customer_cart["cartItems"][0]["variant"]["name"] == "Variant P1 1"
#     assert customer_cart["cartItems"][0]["contractProduct"]["quantityUnit"] == "10"
#     assert (
#         len(customer_cart["cartItems"][0]["contractProduct"]["product"]["variants"])
#         == 3
#     )


# def test_customer_cart_totals(
#     scgp_customer_api_client, scgp_customer_carts, scgp_customer_cart_items
# ):
#     response = scgp_customer_api_client.post_graphql(CUSTOMER_CART_TOTALS_QUERY, {})
#     content = get_graphql_content(response)
#     customer_cart_totals = content["data"]["customerCartTotals"]

#     assert customer_cart_totals["totalContracts"] == 2
#     assert customer_cart_totals["totalProducts"] == 6


# def test_delete_cart_items(
#     scgp_customer_api_client, scgp_customer_carts, scgp_customer_cart_items
# ):
#     variables = {
#         "cartItemIds": [
#             scgp_customer_cart_items[0].id,
#             scgp_customer_cart_items[1].id,
#         ]
#     }

#     response = scgp_customer_api_client.post_graphql(
#         DELETE_CUSTOMER_CART_ITEMS_MUTATION, variables
#     )
#     content = get_graphql_content(response)
#     status = content["data"]["deleteCustomerCartItems"]["status"]

#     assert status == "true"
#     assert len(CustomerCartItem.objects.filter(cart=scgp_customer_carts[0])) == 1


# def test_delete_all_cart_items(
#     scgp_customer_api_client, scgp_customer_carts, scgp_customer_cart_items
# ):
#     """
#     Delete current cart if if all cart items have been deleted
#     """
#     variables = {
#         "cartItemIds": [
#             scgp_customer_cart_items[0].id,
#             scgp_customer_cart_items[1].id,
#             scgp_customer_cart_items[2].id,
#         ]
#     }

#     response = scgp_customer_api_client.post_graphql(
#         DELETE_CUSTOMER_CART_ITEMS_MUTATION, variables
#     )
#     content = get_graphql_content(response)
#     status = content["data"]["deleteCustomerCartItems"]["status"]

#     assert status == "true"
#     assert len(CustomerCartItem.objects.filter(cart=scgp_customer_carts[0])) == 0
#     assert list(CustomerCart.objects.filter(pk=scgp_customer_carts[0].id)) == []


def test_delete_cart_items_fail(
    scgp_customer_api_client, scgp_customer_carts, scgp_customer_cart_items
):
    """
    Delete cart items does not exist or not belong to current user
    """
    variables = {"cartItemIds": [69, 96]}

    response = scgp_customer_api_client.post_graphql(
        DELETE_CUSTOMER_CART_ITEMS_MUTATION, variables
    )
    content = get_graphql_content(response)
    result = content["data"]["deleteCustomerCartItems"]
    message = "Cart items do not exist or belong to another user"

    assert result["status"] is None
    assert result["errors"][0]["message"] == message


# def test_update_customer_cart_success(
#     user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_product_variants,
#     scgp_customer_carts,
#     scgp_customer_cart_items,
#     scgp_customer_products_for_search,
#     scgp_customer_contract_products,
# ):
#     variables = {
#         "id": scgp_customer_carts[1].id,
#         "input": {
#             "lines": [
#                 {
#                     "productId": scgp_customer_products_for_search[1].id,
#                     "quantity": 100,
#                     "variantId": scgp_customer_product_variants[4].id,
#                 },
#                 {
#                     "productId": scgp_customer_products_for_search[1].id,
#                     "quantity": 200,
#                     "variantId": scgp_customer_product_variants[6].id,
#                 },
#             ]
#         },
#     }

#     response = user_api_client.post_graphql(UPDATE_CUSTOMER_CART_MUTATIONS, variables)
#     content = get_graphql_content(response)
#     cart = content["data"]["updateCustomerCart"]["cart"]
#     customer_cart_item1 = CustomerCartItem.objects.filter(
#         cart_id=scgp_customer_carts[1].id,
#         variant_id=scgp_customer_product_variants[4].id,
#     ).first()
#     customer_cart_item2 = CustomerCartItem.objects.filter(
#         cart_id=scgp_customer_carts[1].id,
#         variant_id=scgp_customer_product_variants[6].id,
#     ).first()
#     assert customer_cart_item1.quantity == cart["cartItems"][1]["quantity"]
#     assert customer_cart_item2.quantity == cart["cartItems"][3]["quantity"]


# def test_update_customer_cart_with_quantity_over_remaining(
#     user_api_client,
#     customers_for_search,
#     scgp_customer_contracts,
#     scgp_customer_product_variants,
#     scgp_customer_carts,
#     scgp_customer_cart_items,
#     scgp_customer_products_for_search,
#     scgp_customer_contract_products,
# ):
#     variables = {
#         "id": scgp_customer_carts[1].id,
#         "input": {
#             "lines": [
#                 {
#                     "productId": scgp_customer_products_for_search[1].id,
#                     "quantity": 999999999,
#                     "variantId": scgp_customer_product_variants[4].id,
#                 },
#                 {
#                     "productId": scgp_customer_products_for_search[1].id,
#                     "quantity": 999999999,
#                     "variantId": scgp_customer_product_variants[6].id,
#                 },
#             ]
#         },
#     }

#     response = user_api_client.post_graphql(UPDATE_CUSTOMER_CART_MUTATIONS, variables)
#     message = "Quantity can not over remaining"
#     content = get_graphql_content_from_response(response)
#     error = content["errors"][0]["message"]

#     assert error == message


def test_update_customer_cart_with_quantity_smaller_than_zero(
    user_api_client,
    customers_for_search,
    scgp_customer_contracts,
    scgp_customer_product_variants,
    scgp_customer_carts,
    scgp_customer_cart_items,
    scgp_customer_products_for_search,
    scgp_customer_contract_products,
):
    variables = {
        "id": scgp_customer_carts[1].id,
        "input": {
            "lines": [
                {
                    "productId": scgp_customer_products_for_search[1].id,
                    "quantity": -3,
                    "variantId": scgp_customer_product_variants[4].id,
                },
                {
                    "productId": scgp_customer_products_for_search[1].id,
                    "quantity": -4,
                    "variantId": scgp_customer_product_variants[6].id,
                },
            ]
        },
    }

    response = user_api_client.post_graphql(UPDATE_CUSTOMER_CART_MUTATIONS, variables)
    message = "Quantity must be greater than 0."
    content = get_graphql_content_from_response(response)
    error = content["errors"][0]["message"]

    assert error == message
