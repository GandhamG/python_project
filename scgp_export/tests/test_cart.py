# import mock
import pytest

# from saleor.account.models import User
from saleor.graphql.tests.utils import (  # assert_graphql_error_with_message,
    get_graphql_content,
    get_graphql_content_from_response,
)
from scgp_export.graphql.validators import validate_positive_decimal

# from scgp_export.implementations.carts import create_export_cart
# from scgp_export.models import ExportCart, ExportCartItem, ExportPI, ExportPIProduct
from scgp_export.tests.operations import (  # QUERY_EXPORT_PI,
    CREATE_EXPORT_CART_MUTATIONS,
    UPDATE_EXPORT_CART_MUTATION,
)

# def test_export_pi_query_success(
#     user_api_client,
#     scgp_export_pis,
#     scgp_export_pi_products,
# ):
#     variables = {"id": scgp_export_pis[0].id}
#     response = user_api_client.post_graphql(QUERY_EXPORT_PI, variables)
#     content = get_graphql_content(response)
#     export_pi = ExportPI.objects.get(id=variables["id"])
#     export_pi_products = ExportPIProduct.objects.filter(pi_id=variables["id"]).count()
#     assert content["data"]["exportPi"]["id"] == str(export_pi.id)
#     assert len(content["data"]["exportPi"]["piProducts"]) == export_pi_products


# def test_export_pi_query_null(
#     user_api_client,
#     scgp_export_pis,
#     scgp_export_pi_products,
# ):
#     variables = {"id": 1000}
#     response = user_api_client.post_graphql(QUERY_EXPORT_PI, variables)
#     content = get_graphql_content(response)
#     export_pi_none = ExportPI.objects.filter(id=variables["id"]).first()

#     assert content["data"]["exportPi"] == export_pi_none


# def test_export_pi_query_invalid_field_type(
#     user_api_client,
#     scgp_export_pis,
#     scgp_export_pi_products,
# ):
#     variables = {"id": "abc"}
#     response = user_api_client.post_graphql(QUERY_EXPORT_PI, variables)
#     message = "Field 'id' expected a number but got 'abc'."
#     assert_graphql_error_with_message(response, message)


# def test_create_export_cart_success(
#     user_api_client,
#     scgp_export_sold_tos,
#     scgp_export_products,
#     scgp_export_pis,
#     scgp_export_pi_products,
# ):
#     variables = {
#         "input": {
#             "piId": scgp_export_pis[0].id,
#             "soldToId": scgp_export_sold_tos[0].id,
#             "lines": [
#                 {
#                     "piProductId": scgp_export_pi_products[0].id,
#                     "quantity": 10,
#                 }
#             ],
#         }
#     }
#     response = user_api_client.post_graphql(CREATE_EXPORT_CART_MUTATIONS, variables)
#     content = get_graphql_content(response)
#     export_cart_id = content["data"]["createExportCart"]["cart"]["id"]
#     export_cart_item = content["data"]["createExportCart"]["cart"]["items"]
#     export_cart = ExportCart.objects.get(id=export_cart_id)
#     export_cart_item_count = ExportCartItem.objects.filter(
#         cart_id=export_cart_id
#     ).count()
#     assert export_cart_id == str(export_cart.id)
#     assert export_cart_item_count == len(export_cart_item)


# def test_create_export_cart_invalid_quantity(
#     user_api_client,
#     scgp_export_sold_tos,
#     scgp_export_products,
#     scgp_export_pis,
#     scgp_export_pi_products,
# ):
#     variables = {
#         "input": {
#             "piId": scgp_export_pis[0].id,
#             "soldToId": scgp_export_sold_tos[0].id,
#             "lines": [
#                 {
#                     "piProductId": scgp_export_pi_products[0].id,
#                     "quantity": 1000000000,
#                 }
#             ],
#         }
#     }
#     response = user_api_client.post_graphql(CREATE_EXPORT_CART_MUTATIONS, variables)
#     message = "The input quantity is over the remaining"
#     assert_graphql_error_with_message(response, message)


def test_create_export_cart_invalid_quantity_type(
    user_api_client,
    scgp_export_sold_tos,
    scgp_export_products,
    scgp_export_pis,
    scgp_export_pi_products,
):
    variables = {
        "input": {
            "piId": scgp_export_pis[0].id,
            "soldToId": scgp_export_sold_tos[0].id,
            "lines": [
                {
                    "piProductId": scgp_export_pi_products[0].id,
                    "quantity": -10.5,
                }
            ],
        }
    }
    response = user_api_client.post_graphql(CREATE_EXPORT_CART_MUTATIONS, variables)
    quantity = variables["input"]["lines"][0]["quantity"]
    message = f"Value must be greater than 0. Unsupported value: {quantity}"
    content = get_graphql_content(response)
    assert message == content["data"]["createExportCart"]["errors"][0]["message"]


def test_create_export_cart_missing_field_required(
    user_api_client,
    scgp_export_sold_tos,
    scgp_export_products,
    scgp_export_pis,
    scgp_export_pi_products,
):
    variables = {
        "input": {
            "soldToId": scgp_export_sold_tos[0].id,
            "lines": [
                {
                    "piProductId": scgp_export_pi_products[0].id,
                    "quantity": 10,
                }
            ],
        }
    }
    response = user_api_client.post_graphql(CREATE_EXPORT_CART_MUTATIONS, variables)
    message = 'field "piId": Expected "ID!", found null.'
    content = get_graphql_content_from_response(response)
    assert message in content["errors"][0]["message"]


def test_cart_query_validate_positive_decimal_success():
    quantity = "10.5"
    assert validate_positive_decimal(quantity) == quantity
    assert validate_positive_decimal(float(quantity)) == float(quantity)


def test_contract_query_validate_positive_decimal_invalid_value():
    quantity = "-10.5"
    message = f"Value must be greater than 0. Unsupported value: {quantity}"
    with pytest.raises(Exception) as e:
        validate_positive_decimal(quantity)
    assert message == str(e.value.args[0])


# @mock.patch("scgp_export.implementations.carts.create_or_update_export_cart_items")
# def test_create_export_cart(
#     mock_cart_lines,
#     user_api_client,
#     scgp_export_sold_tos,
#     scgp_export_products,
#     scgp_export_pis,
# ):
#     export_cart_lines = [
#         {
#             "pi_product_id": scgp_export_products[0].id,
#             "quantity": 10,
#         }
#     ]
#     created_by = User.objects.filter(email="test@example.com").first()
#     params = {
#         "pi_id": scgp_export_pis[0].id,
#         "sold_to_id": scgp_export_sold_tos[0].id,
#         "lines": export_cart_lines,
#     }
#     export_cart = create_export_cart(params, created_by)
#     mock_cart_lines.assert_called_once_with(params, export_cart.id)
#     export_cart_last = ExportCart.objects.last()
#     assert export_cart.id == export_cart_last.id


# def test_update_export_cart_success(
#     user_api_client,
#     scgp_export_products,
#     scgp_export_pi_products,
#     scgp_export_carts,
#     scgp_export_cart_items,
# ):
#     variables = {
#         "id": scgp_export_carts[0].id,
#         "input": {
#             "lines": [
#                 {"piProductId": scgp_export_pi_products[0].id, "quantity": 10},
#                 {"piProductId": scgp_export_pi_products[1].id, "quantity": 30},
#             ]
#         },
#     }

#     response = user_api_client.post_graphql(UPDATE_EXPORT_CART_MUTATION, variables)
#     content = get_graphql_content(response)
#     cart = content["data"]["updateExportCart"]["cart"]
#     export_cart_item1 = ExportCartItem.objects.filter(
#         cart_id=scgp_export_carts[0].id,
#         pi_product_id=scgp_export_pi_products[0].id,
#     ).first()
#     export_cart_item2 = ExportCartItem.objects.filter(
#         cart_id=scgp_export_carts[0].id,
#         pi_product_id=scgp_export_pi_products[1].id,
#     ).first()
#     assert export_cart_item1.quantity == cart["items"][0]["quantity"]
#     assert export_cart_item2.quantity == cart["items"][1]["quantity"]


# def test_update_export_cart_with_quantity_over_remaining(
#     user_api_client,
#     scgp_export_products,
#     scgp_export_pi_products,
#     scgp_export_carts,
#     scgp_export_cart_items,
# ):
#     variables = {
#         "id": scgp_export_carts[0].id,
#         "input": {
#             "lines": [
#                 {
#                     "piProductId": scgp_export_pi_products[0].id,
#                     "quantity": 99999999999999999,
#                 },
#                 {
#                     "piProductId": scgp_export_pi_products[1].id,
#                     "quantity": 9999999999999999999,
#                 },
#             ]
#         },
#     }

#     response = user_api_client.post_graphql(UPDATE_EXPORT_CART_MUTATION, variables)
#     message = "The input quantity is over the remaining"
#     content = get_graphql_content_from_response(response)
#     error = content["errors"][0]["message"]

#     assert error == message


def test_update_export_cart_with_quantity_smaller_than_zero(
    user_api_client,
    scgp_export_products,
    scgp_export_pi_products,
    scgp_export_carts,
    scgp_export_cart_items,
):
    variables = {
        "id": scgp_export_carts[0].id,
        "input": {
            "lines": [
                {"piProductId": scgp_export_pi_products[0].id, "quantity": 99},
                {"piProductId": scgp_export_pi_products[1].id, "quantity": -65},
            ]
        },
    }

    response = user_api_client.post_graphql(UPDATE_EXPORT_CART_MUTATION, variables)
    message = "Quantity must be greater than 0."
    content = get_graphql_content_from_response(response)
    error = content["errors"][0]["message"]

    assert error == message
