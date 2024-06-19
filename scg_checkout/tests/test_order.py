# from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from saleor.graphql.tests.utils import (
    get_graphql_content,
    get_graphql_content_from_response,
)
from scg_checkout.contract_order_update import contract_order_delete
from scg_checkout.graphql.helper import resolve_order_line_confirm_qty_after_i_plan_call
from scg_checkout.graphql.validators import to_camel_case, validate_object
from scg_checkout.models import TempOrder, TempOrderLine
from scg_checkout.tests.operations import (  # CONTRACT_DELETE_ORDER_LINES_MUTATION,; CONTRACT_ORDER_CREATE_MUTATION,
    CONTRACT_DELETE_ORDER_LINE_MUTATION,
    CONTRACT_DELETE_ORDER_MUTATION,
    CONTRACT_UPDATE_ORDER_MUTATION,
)

# Start test Create Contract Order
# def test_create_contract_order_success(
#     staff_api_client,
#     customers_for_search,
#     scg_product_variants,
#     scg_checkout_lines,
# ):
#     datetime_now = datetime.utcnow().date()
#     date_time_format = "%Y-%m-%d"
#     po_date = (datetime_now - timedelta(days=10)).strftime(date_time_format)
#     request_date = (datetime_now + timedelta(days=10)).strftime(date_time_format)
#     request_date_line_1 = (datetime_now + timedelta(days=11)).strftime(date_time_format)
#     request_date_line_2 = (datetime_now + timedelta(days=12)).strftime(date_time_format)
#     variables = {
#         "orderInformation": {
#             "customerId": customers_for_search[0].id,
#             "poDate": po_date,
#             "requestDate": request_date,
#         },
#         "lines": [
#             {
#                 "checkoutLineId": scg_checkout_lines[0].id,
#                 "quantity": 10.0,
#                 "requestDate": request_date_line_1,
#                 "plant": "sad",
#                 "shipTo": "zxc",
#                 "internalCommentsToWarehouse": "sad",
#                 "productInformation": "sada",
#                 "variantId": scg_product_variants[0].id,
#             },
#             {
#                 "checkoutLineId": scg_checkout_lines[1].id,
#                 "quantity": 9.5,
#                 "requestDate": request_date_line_2,
#                 "plant": "sad",
#                 "shipTo": "zxc",
#                 "internalCommentsToWarehouse": "sad",
#                 "productInformation": "sada",
#                 "variantId": scg_product_variants[1].id,
#             },
#         ],
#     }

#     response = staff_api_client.post_graphql(
#         CONTRACT_ORDER_CREATE_MUTATION,
#         variables,
#     )

#     data = get_graphql_content(response)["data"]
#     order_data = data["createContractOrder"]["order"]
#     order_object = TempOrder.objects.last()

#     assert order_data["status"] == "draft"
#     assert order_data["customer"]["id"] == str(customers_for_search[0].id)
#     for i in range(2):
#         assert order_data["orderLines"][i]["variant"]["id"] == str(
#             scg_product_variants[i].id
#         )

#     assert str(order_object.status) == order_data["status"]
#     assert str(order_object.customer.id) == order_data["customer"]["id"]
#     order_lines = (
#         TempOrderLine.objects.filter(order__id=order_object.id)
#         .all()
#         .order_by("-quantity")
#     )
#     for i, line in enumerate(order_lines):
#         assert str(line.quantity) == str(order_data["orderLines"][i]["quantity"])
#         assert str(line.variant.id) == str(scg_product_variants[i].id)


# def test_create_contract_order_wrong_type_field_fail(
#     staff_api_client, customers_for_search, scg_product_variants, scg_checkout_lines
# ):
#     datetime_now = datetime.utcnow().date()
#     date_time_format = "%Y-%m-%d"
#     request_date = (datetime_now + timedelta(days=10)).strftime(date_time_format)
#     variables = {
#         "orderInformation": {
#             "customerId": "abc",
#         },
#         "lines": [
#             {
#                 "checkoutLineId": scg_checkout_lines[0].id,
#                 "quantity": "1",
#                 "requestDate": request_date,
#                 "plant": "sad",
#                 "shipTo": 11,
#                 "internalCommentsToWarehouse": "sad",
#                 "productInformation": "sada",
#                 "variantId": "1",
#             },
#         ],
#     }
#     response = staff_api_client.post_graphql(
#         CONTRACT_ORDER_CREATE_MUTATION,
#         variables,
#     )
#     data = get_graphql_content_from_response(response)
#     message = "Field 'id' expected a number but got 'abc'."
#     assert message in data["errors"][0]["message"]
#     assert TempOrder.objects.count() == 0


# def test_create_contract_order_wrong_range_fail(
#     staff_api_client,
#     customers_for_search,
#     scg_product_variants,
#     scg_checkout_lines,
# ):
#     datetime_now = datetime.utcnow().date()
#     date_time_format = "%Y-%m-%d"
#     request_date = (datetime_now + timedelta(days=10)).strftime(date_time_format)
#     variables = {
#         "id": 1,
#         "orderInformation": {
#             "customerId": customers_for_search[0].id,
#         },
#         "lines": [
#             {
#                 "checkoutLineId": scg_checkout_lines[0].id,
#                 "quantity": -10,
#                 "requestDate": request_date,
#                 "plant": "sad",
#                 "shipTo": "zxc",
#                 "internalCommentsToWarehouse": "sad",
#                 "productInformation": "sada",
#                 "variantId": scg_product_variants[0].id,
#             }
#         ],
#     }
#     response = staff_api_client.post_graphql(
#         CONTRACT_ORDER_CREATE_MUTATION,
#         variables,
#     )

#     get_graphql_content_from_response(response)
#     assert TempOrder.objects.count() == 1


# End test Create Contract Order


# Start test Update Contract Order
# def test_update_contract_order_success(
#     staff_api_client,
#     customers_for_search,
#     scg_product_variants,
#     scg_checkout_lines,
#     scg_checkout_orders,
#     scg_checkout_distribution_channel,
#     scg_checkout_sales_organization,
#     scg_checkout_division,
#     scg_checkout_sales_office,
#     scg_checkout_sales_group,
# ):
#     variables = {
#         "id": scg_checkout_orders[1][0].order.id,
#         "input": {
#             "orderOrganizationData": {
#                 "saleOrganizationId": scg_checkout_sales_organization[0].id,
#                 "distributionChannelId": scg_checkout_distribution_channel[0].id,
#                 "divisionId": scg_checkout_division[0].id,
#                 "saleOfficeId": scg_checkout_sales_office[0].id,
#                 "saleGroupId": scg_checkout_sales_group[0].id,
#             },
#             "orderInformation": {
#                 "customerId": scg_checkout_orders[0][0].customer_id,
#                 "poDate": "2022-10-10",
#                 "requestDate": "2022-05-18",
#                 "orderType": "ZTA",
#                 "shipTo": "shipTosadasdsa18",
#                 "billTo": "billToasdsadas18",
#                 "internalCommentsToWarehouse": "internalCommentsToWarehouseasdsadsa18",
#                 "internalCommentsToLogistic": "internalCommentsToLogisticasdsadas18",
#                 "externalCommentsToCustomer": "externalCommentsToCustomerasdasd18",
#                 "productInformation": "productInformationasdsa18",
#             },
#             "lines": [
#                 {
#                     "checkoutLineId": scg_checkout_lines[0].id,
#                     "quantity": 10,
#                     "requestDate": "2022-12-12",
#                     "plant": "sad",
#                     "productInformation": "sada",
#                     "variantId": scg_product_variants[0].id,
#                     "id": scg_checkout_orders[1][0].id,
#                 },
#             ],
#             "status": "DRAFT",
#         },
#     }
#     response = staff_api_client.post_graphql(
#         CONTRACT_UPDATE_ORDER_MUTATION,
#         variables,
#     )

#     data = get_graphql_content(response)["data"]
#     update_contract_order = data["updateContractOrder"]
#     order = update_contract_order["order"]
#     customer = order["customer"]
#     order_lines = order["orderLines"]

#     assert order["id"] == str(scg_checkout_orders[1][0].order.id)
#     assert customer["id"] == str(scg_checkout_orders[0][0].customer_id)
#     assert order_lines[0]["id"] == str(scg_checkout_orders[1][0].id)
#     order_object = TempOrder.objects.filter(id=order["id"]).first()
#     assert (
#         (str(order_object.id) == order["id"])
#         and (str(order_object.po_date) == "2022-10-10")
#         and (str(order_object.customer.id) == customer["id"])
#     )


def test_update_contract_order_wrong_type_order_id_fail(
    staff_api_client,
    customers_for_search,
    scg_product_variants,
    scg_checkout_lines,
    scg_checkout_orders,
    scg_checkout_distribution_channel,
    scg_checkout_sales_organization,
    scg_checkout_division,
    scg_checkout_sales_office,
    scg_checkout_sales_group,
):
    variables = {
        "id": "abc",
        "input": {
            "orderOrganizationData": {
                "saleOrganizationId": scg_checkout_sales_organization[0].id,
                "distributionChannelId": scg_checkout_distribution_channel[0].id,
                "divisionId": scg_checkout_division[0].id,
                "saleOfficeId": scg_checkout_sales_office[0].id,
                "saleGroupId": scg_checkout_sales_group[0].id,
            },
            "orderInformation": {
                "customerId": scg_checkout_orders[0][0].customer_id,
                "poDate": "2022-10-10",
                "requestDate": "2022-05-18",
                "orderType": "ZTA",
                "shipTo": "shipTosadasdsa18",
                "billTo": "billToasdsadas18",
                "internalCommentsToWarehouse": "internalCommentsToWarehouseasdsadsa18",
                "internalCommentsToLogistic": "internalCommentsToLogisticasdsadas18",
                "externalCommentsToCustomer": "externalCommentsToCustomerasdasd18",
                "productInformation": "productInformationasdsa18",
            },
            "lines": [
                {
                    "checkoutLineId": scg_checkout_lines[0].id,
                    "quantity": 10,
                    "requestDate": "2022-12-12",
                    "plant": "sad",
                    "productInformation": "sada",
                    "variantId": scg_product_variants[0].id,
                    "id": scg_checkout_orders[1][0].id,
                },
            ],
            "status": "DRAFT",
        },
    }
    response = staff_api_client.post_graphql(
        CONTRACT_UPDATE_ORDER_MUTATION,
        variables,
    )

    data = get_graphql_content_from_response(response)
    errors = data["errors"]
    message = errors[0]["message"]
    assert "Field 'id' expected a number but got 'abc'" in message


# def test_update_contract_order_wrong_range_order_id_fail(
#     staff_api_client,
#     customers_for_search,
#     scg_product_variants,
#     scg_checkout_lines,
#     scg_checkout_orders,
#     scg_checkout_distribution_channel,
#     scg_checkout_sales_organization,
#     scg_checkout_division,
#     scg_checkout_sales_office,
#     scg_checkout_sales_group,
# ):
#     variables = {
#         "id": -100,
#         "input": {
#             "orderOrganizationData": {
#                 "saleOrganizationId": scg_checkout_sales_organization[0].id,
#                 "distributionChannelId": scg_checkout_distribution_channel[0].id,
#                 "divisionId": scg_checkout_division[0].id,
#                 "saleOfficeId": scg_checkout_sales_office[0].id,
#                 "saleGroupId": scg_checkout_sales_group[0].id,
#             },
#             "orderInformation": {
#                 "customerId": scg_checkout_orders[0][0].customer_id,
#                 "poDate": "2022-10-10",
#                 "requestDate": "2022-05-18",
#                 "orderType": "ZTA",
#                 "shipTo": "shipTosadasdsa18",
#                 "billTo": "billToasdsadas18",
#                 "internalCommentsToWarehouse": "internalCommentsToWarehouseasdsadsa18",
#                 "internalCommentsToLogistic": "internalCommentsToLogisticasdsadas18",
#                 "externalCommentsToCustomer": "externalCommentsToCustomerasdasd18",
#                 "productInformation": "productInformationasdsa18",
#             },
#             "lines": [
#                 {
#                     "checkoutLineId": scg_checkout_lines[0].id,
#                     "quantity": 10,
#                     "requestDate": "2022-12-12",
#                     "plant": "sad",
#                     "productInformation": "sada",
#                     "variantId": scg_product_variants[0].id,
#                     "id": scg_checkout_orders[1][0].id,
#                 },
#             ],
#             "status": "DRAFT",
#         },
#     }
#     response = staff_api_client.post_graphql(
#         CONTRACT_UPDATE_ORDER_MUTATION,
#         variables,
#     )

#     data = get_graphql_content_from_response(response)
#     errors = data["errors"]
#     message = errors[0]["message"]
#     assert "TempOrder matching query does not exist." in message


# def test_delete_contract_order_success(staff_api_client, scg_checkout_orders):
#     variables = {"id": scg_checkout_orders[0][0].id}
#     response = staff_api_client.post_graphql(
#         CONTRACT_DELETE_ORDER_MUTATION,
#         variables,
#     )
#     data = get_graphql_content_from_response(response)["data"]
#     assert data["deleteContractOrder"]["order"]["id"] is None
#     remove_data = TempOrder.objects.filter(id=variables["id"])
#     assert len(remove_data) == 0
#     assert TempOrder.objects.count() == 2
#     assert TempOrder.objects.filter(id=variables["id"]).count() == 0


def test_delete_contract_order_missing_field_fail(
    staff_api_client, scg_checkout_orders
):
    variables = {}
    response = staff_api_client.post_graphql(
        CONTRACT_DELETE_ORDER_MUTATION,
        variables,
    )
    data = get_graphql_content_from_response(response)
    error = data["errors"]
    message = error[0]["message"]
    assert (
        'Argument "id" of required type ID!" provided the variable "$id" which was not provided'
        in message
    )
    assert TempOrder.objects.count() == 3


def test_delete_contract_order_wrong_range_foreign_key_fail(
    staff_api_client, scg_checkout_orders
):
    variables = {"id": "1000000"}
    response = staff_api_client.post_graphql(
        CONTRACT_DELETE_ORDER_MUTATION,
        variables,
    )
    data = get_graphql_content(response)["data"]
    assert data["deleteContractOrder"]["order"]["id"] is None
    assert TempOrder.objects.count() == 3


def test_delete_contract_order_wrong_type_field_fail(
    staff_api_client, scg_checkout_orders
):
    variables = {"id": "abc"}
    response = staff_api_client.post_graphql(
        CONTRACT_DELETE_ORDER_MUTATION,
        variables,
    )
    data = get_graphql_content_from_response(response)
    errors = data["errors"]
    message = errors[0]["message"]
    assert "Field 'id' expected a number but got 'abc'" in message
    assert TempOrder.objects.count() == 3


# def test_delete_contract_order_lines_success(staff_api_client, scg_checkout_orders):
#     variables = {"ids": [scg_checkout_orders[1][0].id, scg_checkout_orders[1][1].id]}
#     response = staff_api_client.post_graphql(
#         CONTRACT_DELETE_ORDER_LINES_MUTATION,
#         variables,
#     )
#     data = get_graphql_content(response)["data"]
#     assert data["deleteContractOrderLines"]["orderLines"]["id"] is None
#     assert TempOrderLine.objects.count() == 4
#     assert TempOrderLine.objects.filter(id__in=variables["ids"]).count() == 0


# def test_delete_contract_order_lines_wrong_range_foreign_key_fail(
#     staff_api_client, scg_checkout_orders
# ):
#     variables = {"ids": [scg_checkout_orders[1][0].id, -99]}
#     response = staff_api_client.post_graphql(
#         CONTRACT_DELETE_ORDER_LINES_MUTATION,
#         variables,
#     )
#     data = get_graphql_content_from_response(response)["data"]
#     assert data["deleteContractOrderLines"]["orderLines"]["id"] is None
#     assert TempOrderLine.objects.count() == 5
#     assert TempOrderLine.objects.filter(id__in=variables["ids"]).count() == 0


# def test_delete_contract_order_line_success(staff_api_client, scg_checkout_orders):
#     variables = {"id": scg_checkout_orders[1][0].id}
#     response = staff_api_client.post_graphql(
#         CONTRACT_DELETE_ORDER_LINE_MUTATION,
#         variables,
#     )
#     data = get_graphql_content(response)["data"]
#     assert data["deleteContractOrderLine"]["orderLine"]["id"] is None
#     remove_data = TempOrderLine.objects.filter(id=variables["id"])
#     assert len(remove_data) == 0
#     assert TempOrderLine.objects.count() == 5


def test_delete_contract_order_line_wrong_type_field_fail(
    staff_api_client, scg_checkout_orders
):
    variables = {"id": "abc"}
    response = staff_api_client.post_graphql(
        CONTRACT_DELETE_ORDER_LINE_MUTATION,
        variables,
    )
    data = get_graphql_content_from_response(response)
    errors = data["errors"]
    message = errors[0]["message"]
    assert "Field 'id' expected a number but got 'abc'." in message
    assert TempOrderLine.objects.count() == 6


# def test_delete_contract_order_line_wrong_range_foreign_key_fail(
#     staff_api_client, scg_checkout_orders
# ):
#     variables = {"id": scg_checkout_orders[1][0].id}
#     response = staff_api_client.post_graphql(
#         CONTRACT_DELETE_ORDER_LINE_MUTATION,
#         variables,
#     )
#     data = get_graphql_content_from_response(response)["data"]
#     assert data["deleteContractOrderLine"]["orderLine"]["id"] is None
#     assert TempOrderLine.objects.count() == 5


def test_to_camel_case_to_prefix():
    _snake = "validate_"
    camel_data = "validate"
    camel = to_camel_case(_snake)
    assert camel == camel_data


def test_to_camel_case_two_prefix():
    _snake = "validate__"
    camel_data = "validate"
    camel = to_camel_case(_snake)
    assert camel == camel_data


def test_to_camel_case_with_prefix():
    _snake = "validate_data"
    camel_data = "validateData"
    camel = to_camel_case(_snake)
    assert camel == camel_data


@patch("scg_checkout.graphql.validators.to_camel_case")
def test_validate_object_when_no_object(to_camel_case_mock):
    to_camel_case_mock.return_value = "dataObject"
    with pytest.raises(ValidationError) as e:
        validate_object({}, "data_object", ["first_field"])
    assert e.value.message == "dataObject is required!"
    to_camel_case_mock.assert_has_calls([mock.call("data_object")])


@patch("scg_checkout.graphql.validators.to_camel_case")
def test_validate_object_when_missing_field(to_camel_case_mock, data):
    to_camel_case_mock.side_effect = ["firstField", "dataObject"]
    with pytest.raises(ValidationError) as e:
        validate_object(data, "data_object", ["first_field"])
    assert e.value.message == "firstField in dataObject is required!"
    to_camel_case_mock.assert_has_calls(
        [mock.call("first_field"), mock.call("data_object")]
    )


def test_validate_contract_order_delete_wrong_type_field():
    order_id = "abc"
    with pytest.raises(Exception) as e:
        contract_order_delete(order_id)
    message = "Field 'id' expected a number but got 'abc'."
    assert str(e.value.args[0]) == message


def test_on_hand_stock_flag_domestic_order_check():
    # Test case 1: on_hand_stock is None
    order_line_qty = 10
    order_schedules_in = {"confirmQty": 5}
    order_schedules_inx = {"confirmQty": False}
    resolve_order_line_confirm_qty_after_i_plan_call(
        order_line_qty, order_schedules_in, order_schedules_inx
    )
    assert order_schedules_in["confirmQty"] == 5  # confirmQty should remain unchanged
    assert (
        order_schedules_inx["confirmQty"] == False
    )  # confirmQty should remain unchanged

    # Test case 2: on_hand_stock is False
    resolve_order_line_confirm_qty_after_i_plan_call(
        order_line_qty, order_schedules_in, order_schedules_inx, on_hand_stock=False
    )
    assert order_schedules_in["confirmQty"] == 0  # confirmQty should be set to 0
    # Test case 3: on_hand_stock is True
    resolve_order_line_confirm_qty_after_i_plan_call(
        order_line_qty, order_schedules_in, order_schedules_inx, on_hand_stock=True
    )
    assert order_schedules_in["confirmQty"] == 10
