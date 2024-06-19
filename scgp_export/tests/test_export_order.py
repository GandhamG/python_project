from django.utils import timezone
from freezegun import freeze_time
from pytz import UTC

from saleor.graphql.tests.utils import (
    assert_graphql_error_with_message,
    get_graphql_content,
)

# from scgp_export import models
# from scgp_export.graphql.enums import ScgExportRejectReason, ScgpExportOrderStatus
from scgp_export.tests.operations import (
    CREATE_EXPORT_ORDER,
    UPDATE_ALL_EXPORT_ORDER_LINES_MUTATION,
    UPDATE_EXPORT_ORDER_LINES_MUTATION,
    UPDATE_EXPORT_ORDER_MUTATION,
)

# def test_create_order_success(
#     user1_logged, scgp_export_pis, scgp_export_cart_items, scgp_export_pi_products
# ):
#     variables = {
#         "input": {
#             "orderHeader": {"piId": scgp_export_pis[0].id},
#             "lines": [
#                 {
#                     "cartItemId": scgp_export_cart_items[0].id,
#                     "piProduct": scgp_export_pi_products[0].id,
#                     "quantity": 10.5,
#                 },
#                 {
#                     "cartItemId": scgp_export_cart_items[1].id,
#                     "piProduct": scgp_export_pi_products[1].id,
#                     "quantity": 15.5,
#                 },
#             ],
#         }
#     }

#     response = user1_logged.post_graphql(CREATE_EXPORT_ORDER, variables=variables)
#     content = get_graphql_content(response)
#     create_export_order = content["data"]["createExportOrder"]["order"]
#     errors = content["data"]["createExportOrder"]["errors"]

#     assert len(errors) == 0
#     assert create_export_order["pi"]["id"] == str(scgp_export_pis[0].id)
#     assert create_export_order["pi"]["code"] == str(scgp_export_pis[0].code)
#     assert (
#         create_export_order["netPrice"]
#         == scgp_export_pi_products[0].price_per_unit * 10.5
#         + scgp_export_pi_products[1].price_per_unit * 15.5
#     )
#     assert (
#         create_export_order["lines"]["edges"][0]["node"]["netPrice"]
#         == scgp_export_pi_products[0].price_per_unit * 10.5
#     )
#     assert (
#         create_export_order["lines"]["edges"][0]["node"]["materialCode"]
#         <= create_export_order["lines"]["edges"][1]["node"]["materialCode"]
#     )


# def test_create_order_success_with_out_cart_item(
#     user1_logged, scgp_export_pis, scgp_export_cart_items, scgp_export_pi_products
# ):
#     variables = {
#         "input": {
#             "orderHeader": {"piId": scgp_export_pis[0].id},
#             "lines": [
#                 {
#                     "piProduct": scgp_export_pi_products[0].id,
#                     "quantity": 10.5,
#                 },
#                 {
#                     "piProduct": scgp_export_pi_products[1].id,
#                     "quantity": 15.5,
#                 },
#             ],
#         }
#     }

#     response = user1_logged.post_graphql(CREATE_EXPORT_ORDER, variables=variables)
#     content = get_graphql_content(response)
#     create_export_order = content["data"]["createExportOrder"]["order"]
#     errors = content["data"]["createExportOrder"]["errors"]

#     assert len(errors) == 0
#     assert create_export_order["pi"]["id"] == str(scgp_export_pis[0].id)
#     assert create_export_order["pi"]["code"] == str(scgp_export_pis[0].code)
#     assert (
#         create_export_order["netPrice"]
#         == scgp_export_pi_products[0].price_per_unit * 10.5
#         + scgp_export_pi_products[1].price_per_unit * 15.5
#     )
#     assert (
#         create_export_order["lines"]["edges"][0]["node"]["netPrice"]
#         == scgp_export_pi_products[0].price_per_unit * 10.5
#     )
#     assert (
#         create_export_order["lines"]["edges"][0]["node"]["materialCode"]
#         <= create_export_order["lines"]["edges"][1]["node"]["materialCode"]
#     )


def test_create_order_error_zero_quantity(
    user1_logged, scgp_export_pis, scgp_export_cart_items, scgp_export_pi_products
):
    variables = {
        "input": {
            "orderHeader": {"piId": scgp_export_pis[0].id},
            "lines": [
                {
                    "cartItemId": scgp_export_cart_items[0].id,
                    "piProduct": scgp_export_pi_products[0].id,
                    "quantity": 0,
                }
            ],
        }
    }

    response = user1_logged.post_graphql(CREATE_EXPORT_ORDER, variables=variables)
    content = get_graphql_content(response)
    create_export_order = content["data"]["createExportOrder"]["order"]
    errors = content["data"]["createExportOrder"]["errors"]

    assert errors[0]["field"] == "quantity"
    assert errors[0]["message"] == "The quantity must be greater than 0"
    assert create_export_order is None


# def test_create_order_error_pi_not_exist(
#     user1_logged, scgp_export_pis, scgp_export_cart_items, scgp_export_pi_products
# ):
#     variables = {
#         "input": {
#             "orderHeader": {"piId": 12345},
#             "lines": [
#                 {
#                     "cartItemId": scgp_export_cart_items[0].id,
#                     "piProduct": scgp_export_pi_products[0].id,
#                     "quantity": 10,
#                 }
#             ],
#         }
#     }

#     response = user1_logged.post_graphql(CREATE_EXPORT_ORDER, variables=variables)
#     message = "ExportPI matching query does not exist."
#     assert_graphql_error_with_message(response, message)


# def test_create_order_error_pi_product_not_exist(
#     user1_logged, scgp_export_pis, scgp_export_cart_items, scgp_export_pi_products
# ):
#     variables = {
#         "input": {
#             "orderHeader": {"piId": scgp_export_pis[0].id},
#             "lines": [
#                 {
#                     "cartItemId": scgp_export_cart_items[0].id,
#                     "piProduct": 12345,
#                     "quantity": 10.5,
#                 }
#             ],
#         }
#     }

#     response = user1_logged.post_graphql(CREATE_EXPORT_ORDER, variables=variables)
#     message = "ExportPIProduct matching query does not exist."
#     assert_graphql_error_with_message(response, message)


def test_create_order_error_user_not_login(
    api_client, scgp_export_pis, scgp_export_cart_items, scgp_export_pi_products
):
    variables = {
        "input": {
            "orderHeader": {"piId": scgp_export_pis[0].id},
            "lines": [
                {
                    "cartItemId": scgp_export_cart_items[0].id,
                    "piProduct": scgp_export_pi_products[0].id,
                    "quantity": 10.5,
                },
            ],
        }
    }

    response = api_client.post_graphql(CREATE_EXPORT_ORDER, variables=variables)
    message = "You need one of the following permissions: AUTHENTICATED_USER"
    assert_graphql_error_with_message(response, message)


# def test_update_export_order_success(
#     user1_logged,
#     scgp_export_orders,
#     scg_checkout_sales_organization,
#     scg_checkout_distribution_channel,
#     scg_checkout_division,
#     scg_checkout_sales_office,
#     scg_checkout_sales_group,
# ):
#     order_id = scgp_export_orders[0].id
#     variables = {
#         "id": order_id,
#         "input": {
#             "agency": {
#                 "orderType": "ZOR",
#                 "salesOrganizationId": scg_checkout_sales_organization[1].id,
#                 "distributionChannelId": scg_checkout_distribution_channel[1].id,
#                 "divisionId": scg_checkout_division[1].id,
#                 "salesOfficeId": scg_checkout_sales_office[1].id,
#                 "salesGroupId": scg_checkout_sales_group[1].id,
#             },
#             "orderHeader": {
#                 "poDate": "2022-08-10",
#                 "poNo": "poNo2",
#                 "requestDate": "2022-08-20",
#                 "refPiNo": "refPiNo2",
#                 "usage": "usage2",
#                 "unloadingPoint": "unloadingPoint2",
#                 "placeOfDelivery": "placeOfDelivery2",
#                 "portOfDischarge": "portOfDischarge2",
#                 "portOfLoading": "portOfLoading2",
#                 "noOfContainers": "noOfContainers2",
#                 "uom": "uom2",
#                 "gwUom": "gwUom2",
#                 "etd": "etd2",
#                 "eta": "eta2",
#                 "dlcExpiryDate": "2022-08-30",
#                 "dlcNo": "dlcNo2",
#                 "dlcLatestDeliveryDate": "2022-08-30",
#                 "description": "description2",
#                 "payer": "payer2",
#                 "endCustomer": "endCustomer2",
#                 "paymentInstruction": "paymentInstruction2",
#                 "remark": "remark2",
#                 "productionInformation": "productionInformation2",
#                 "internalCommentToWarehouse": "internalCommentToWarehouse2",
#             },
#             "status": "DRAFT",
#         },
#     }
#     request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
#     with freeze_time(request_time):
#         response = user1_logged.post_graphql(
#             UPDATE_EXPORT_ORDER_MUTATION, variables=variables
#         )
#     content = get_graphql_content(response)
#     errors = content["data"]["updateExportOrder"]["errors"]

#     order = models.ExportOrder.objects.get(id=order_id)

#     assert len(errors) == 0
#     assert order.order_type == variables["input"]["agency"]["orderType"]
#     assert (
#         order.sales_organization.id
#         == variables["input"]["agency"]["salesOrganizationId"]
#     )
#     assert (
#         order.distribution_channel.id
#         == variables["input"]["agency"]["distributionChannelId"]
#     )
#     assert order.division.id == variables["input"]["agency"]["divisionId"]
#     assert order.sales_office.id == variables["input"]["agency"]["salesOfficeId"]
#     assert order.sales_group.id == variables["input"]["agency"]["salesGroupId"]
#     assert (
#         order.po_date.strftime("%Y-%m-%d")
#         == variables["input"]["orderHeader"]["poDate"]
#     )
#     assert order.po_no == variables["input"]["orderHeader"]["poNo"]
#     assert (
#         order.request_date.strftime("%Y-%m-%d")
#         == variables["input"]["orderHeader"]["requestDate"]
#     )
#     assert order.ref_pi_no == variables["input"]["orderHeader"]["refPiNo"]
#     assert order.usage == variables["input"]["orderHeader"]["usage"]
#     assert order.unloading_point == variables["input"]["orderHeader"]["unloadingPoint"]
#     assert (
#         order.place_of_delivery == variables["input"]["orderHeader"]["placeOfDelivery"]
#     )
#     assert (
#         order.port_of_discharge == variables["input"]["orderHeader"]["portOfDischarge"]
#     )
#     assert order.port_of_loading == variables["input"]["orderHeader"]["portOfLoading"]
#     assert order.no_of_containers == variables["input"]["orderHeader"]["noOfContainers"]
#     assert order.uom == variables["input"]["orderHeader"]["uom"]
#     assert order.gw_uom == variables["input"]["orderHeader"]["gwUom"]
#     assert order.etd == variables["input"]["orderHeader"]["etd"]
#     assert order.eta == variables["input"]["orderHeader"]["eta"]
#     assert (
#         order.dlc_expiry_date.strftime("%Y-%m-%d")
#         == variables["input"]["orderHeader"]["dlcExpiryDate"]
#     )
#     assert order.dlc_no == variables["input"]["orderHeader"]["dlcNo"]
#     assert (
#         order.dlc_latest_delivery_date.strftime("%Y-%m-%d")
#         == variables["input"]["orderHeader"]["dlcLatestDeliveryDate"]
#     )
#     assert order.description == variables["input"]["orderHeader"]["description"]
#     assert order.payer == variables["input"]["orderHeader"]["payer"]
#     assert order.end_customer == variables["input"]["orderHeader"]["endCustomer"]
#     assert (
#         order.payment_instruction
#         == variables["input"]["orderHeader"]["paymentInstruction"]
#     )
#     assert order.remark == variables["input"]["orderHeader"]["remark"]
#     assert (
#         order.production_information
#         == variables["input"]["orderHeader"]["productionInformation"]
#     )
#     assert (
#         order.internal_comment_to_warehouse
#         == variables["input"]["orderHeader"]["internalCommentToWarehouse"]
#     )
#     assert order.updated_at == request_time


# def test_update_export_order_error_order_not_exist(
#     user1_logged,
#     scgp_export_orders,
#     scg_checkout_sales_organization,
#     scg_checkout_distribution_channel,
#     scg_checkout_division,
#     scg_checkout_sales_office,
#     scg_checkout_sales_group,
# ):
#     order_id = 100
#     variables = {
#         "id": order_id,
#         "input": {
#             "agency": {
#                 "orderType": "ZOR",
#                 "salesOrganizationId": scg_checkout_sales_organization[1].id,
#                 "distributionChannelId": scg_checkout_distribution_channel[1].id,
#                 "divisionId": scg_checkout_division[1].id,
#                 "salesOfficeId": scg_checkout_sales_office[1].id,
#                 "salesGroupId": scg_checkout_sales_group[1].id,
#             },
#             "orderHeader": {
#                 "poDate": "2022-08-10",
#                 "poNo": "poNo2",
#                 "requestDate": "2022-08-20",
#                 "refPiNo": "refPiNo2",
#                 "usage": "usage2",
#                 "unloadingPoint": "unloadingPoint2",
#                 "placeOfDelivery": "placeOfDelivery2",
#                 "portOfDischarge": "portOfDischarge2",
#                 "portOfLoading": "portOfLoading2",
#                 "noOfContainers": "noOfContainers2",
#                 "uom": "uom2",
#                 "gwUom": "gwUom2",
#                 "etd": "etd2",
#                 "eta": "eta2",
#                 "dlcExpiryDate": "2022-08-30",
#                 "dlcNo": "dlcNo2",
#                 "dlcLatestDeliveryDate": "2022-08-30",
#                 "description": "description2",
#                 "payer": "payer2",
#                 "endCustomer": "endCustomer2",
#                 "paymentInstruction": "paymentInstruction2",
#                 "remark": "remark2",
#                 "productionInformation": "productionInformation2",
#                 "internalCommentToWarehouse": "internalCommentToWarehouse2",
#             },
#             "status": "DRAFT",
#         },
#     }

#     request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
#     with freeze_time(request_time):
#         response = user1_logged.post_graphql(
#             UPDATE_EXPORT_ORDER_MUTATION, variables=variables
#         )
#     message = "ExportOrder matching query does not exist."
#     assert_graphql_error_with_message(response, message)


def test_update_export_order_error_user_not_login(
    api_client,
    scgp_export_orders,
    scg_checkout_sales_organization,
    scg_checkout_distribution_channel,
    scg_checkout_division,
    scg_checkout_sales_office,
    scg_checkout_sales_group,
):
    order_id = scgp_export_orders[0].id
    variables = {
        "id": order_id,
        "input": {
            "agency": {
                "orderType": "ZOR",
                "salesOrganizationId": scg_checkout_sales_organization[1].id,
                "distributionChannelId": scg_checkout_distribution_channel[1].id,
                "divisionId": scg_checkout_division[1].id,
                "salesOfficeId": scg_checkout_sales_office[1].id,
                "salesGroupId": scg_checkout_sales_group[1].id,
            },
            "orderHeader": {
                "poDate": "2022-08-10",
                "poNo": "poNo2",
                "requestDate": "2022-08-20",
                "refPiNo": "refPiNo2",
                "usage": "usage2",
                "unloadingPoint": "unloadingPoint2",
                "placeOfDelivery": "placeOfDelivery2",
                "portOfDischarge": "portOfDischarge2",
                "portOfLoading": "portOfLoading2",
                "noOfContainers": "noOfContainers2",
                "uom": "uom2",
                "gwUom": "gwUom2",
                "etd": "etd2",
                "eta": "eta2",
                "dlcExpiryDate": "2022-08-30",
                "dlcNo": "dlcNo2",
                "dlcLatestDeliveryDate": "2022-08-30",
                "description": "description2",
                "payer": "payer2",
                "endCustomer": "endCustomer2",
                "paymentInstruction": "paymentInstruction2",
                "remark": "remark2",
                "productionInformation": "productionInformation2",
                "internalCommentToWarehouse": "internalCommentToWarehouse2",
            },
            "status": "DRAFT",
        },
    }
    request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
    with freeze_time(request_time):
        response = api_client.post_graphql(
            UPDATE_EXPORT_ORDER_MUTATION, variables=variables
        )
    message = "You need one of the following permissions: AUTHENTICATED_USER"
    assert_graphql_error_with_message(response, message)


# def test_update_export_order_error_request_date(
#     user1_logged,
#     scgp_export_orders,
#     scg_checkout_sales_organization,
#     scg_checkout_distribution_channel,
#     scg_checkout_division,
#     scg_checkout_sales_office,
#     scg_checkout_sales_group,
# ):
#     order_id = scgp_export_orders[0].id
#     variables = {
#         "id": order_id,
#         "input": {
#             "agency": {
#                 "orderType": "ZOR",
#                 "salesOrganizationId": scg_checkout_sales_organization[1].id,
#                 "distributionChannelId": scg_checkout_distribution_channel[1].id,
#                 "divisionId": scg_checkout_division[1].id,
#                 "salesOfficeId": scg_checkout_sales_office[1].id,
#                 "salesGroupId": scg_checkout_sales_group[1].id,
#             },
#             "orderHeader": {
#                 "poDate": "2022-08-01",
#                 "poNo": "poNo2",
#                 "requestDate": "2022-08-01",
#                 "refPiNo": "refPiNo2",
#                 "usage": "usage2",
#                 "unloadingPoint": "unloadingPoint2",
#                 "placeOfDelivery": "placeOfDelivery2",
#                 "portOfDischarge": "portOfDischarge2",
#                 "portOfLoading": "portOfLoading2",
#                 "noOfContainers": "noOfContainers2",
#                 "uom": "uom2",
#                 "gwUom": "gwUom2",
#                 "etd": "etd2",
#                 "eta": "eta2",
#                 "dlcExpiryDate": "2022-08-01",
#                 "dlcNo": "dlcNo2",
#                 "dlcLatestDeliveryDate": "2022-08-01",
#                 "description": "description2",
#                 "payer": "payer2",
#                 "endCustomer": "endCustomer2",
#                 "paymentInstruction": "paymentInstruction2",
#                 "remark": "remark2",
#                 "productionInformation": "productionInformation2",
#                 "internalCommentToWarehouse": "internalCommentToWarehouse2",
#             },
#             "status": "DRAFT",
#         },
#     }
#     request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
#     with freeze_time(request_time):
#         response = user1_logged.post_graphql(
#             UPDATE_EXPORT_ORDER_MUTATION, variables=variables
#         )
#     content = get_graphql_content(response)
#     errors = content["data"]["updateExportOrder"]["errors"]
#     order = content["data"]["updateExportOrder"]["order"]
#     message = "Request date must be further than today"

#     assert order is None
#     assert errors[0]["message"] == message


# def test_update_order_line_for_completed_order(
#     user1_logged, scgp_export_orders, scgp_export_order_lines, scgp_export_pi_products
# ):
#     order_id = scgp_export_orders[2].id
#     update_line_id = scgp_export_order_lines[6].id
#     old_remaining_qty = scgp_export_order_lines[6].pi_product.remaining_quantity
#     old_order_line_qty = scgp_export_order_lines[6].quantity
#     variables = {
#         "id": order_id,
#         "input": [
#             {
#                 "id": update_line_id,
#                 "quantity": 9,
#                 "quantityUnit": "Unit2",
#                 "weightUnit": "Weight2",
#                 "itemCatEo": "itemCatEo2",
#                 "plant": "plant2",
#                 "refPiNo": "refPiNo2",
#                 "requestDate": "2022-09-01",
#                 "route": "route2",
#                 "deliveryTolOver": 100.5,
#                 "deliveryTolUnder": 200.5,
#                 "deliveryTolUnlimited": False,
#                 "rollDiameter": 69,
#                 "rollCoreDiameter": 96.5,
#                 "rollQuantity": 100,
#                 "rollPerPallet": 96,
#                 "palletSize": "palletSize2",
#                 "palletNo": "palletNo2",
#                 "packageQuantity": 96.9,
#                 "packingList": "packingList2",
#                 "shippingPoint": "Shipping point2",
#                 "remark": "remark2",
#                 "rejectReason": "NO",
#             }
#         ],
#     }
#     request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
#     with freeze_time(request_time):
#         response = user1_logged.post_graphql(
#             UPDATE_EXPORT_ORDER_LINES_MUTATION, variables
#         )
#     content = get_graphql_content(response)
#     errors = content["data"]["updateExportOrderLines"]["errors"]
#     updated_order_line_object = models.ExportOrderLine.objects.get(id=update_line_id)
#     assert len(errors) == 0
#     assert scgp_export_orders[2].status == ScgpExportOrderStatus.CONFIRMED.value

#     new_remaining_qty = (
#         float(old_remaining_qty)
#         + float(old_order_line_qty)
#         - float(variables["input"][0]["quantity"])
#     )
#     assert updated_order_line_object.pi_product.remaining_quantity == new_remaining_qty

#     assert updated_order_line_object.quantity == variables["input"][0]["quantity"]
#     assert (
#         updated_order_line_object.quantity_unit == variables["input"][0]["quantityUnit"]
#     )
#     assert updated_order_line_object.weight_unit == variables["input"][0]["weightUnit"]
#     assert updated_order_line_object.item_cat_eo == variables["input"][0]["itemCatEo"]
#     assert updated_order_line_object.plant == variables["input"][0]["plant"]
#     assert updated_order_line_object.ref_pi_no == variables["input"][0]["refPiNo"]
#     assert (
#         updated_order_line_object.request_date.strftime("%Y-%m-%d")
#         == variables["input"][0]["requestDate"]
#     )
#     assert (
#         updated_order_line_object.reject_reason
#         == ScgExportRejectReason[variables["input"][0]["rejectReason"]].value
#     )
#     assert updated_order_line_object.route == variables["input"][0]["route"]
#     assert (
#         updated_order_line_object.roll_quantity == variables["input"][0]["rollQuantity"]
#     )
#     assert (
#         updated_order_line_object.roll_diameter == variables["input"][0]["rollDiameter"]
#     )
#     assert (
#         updated_order_line_object.roll_core_diameter
#         == variables["input"][0]["rollCoreDiameter"]
#     )
#     assert updated_order_line_object.remark == variables["input"][0]["remark"]
#     assert (
#         updated_order_line_object.roll_per_pallet
#         == variables["input"][0]["rollPerPallet"]
#     )
#     assert updated_order_line_object.pallet_size == variables["input"][0]["palletSize"]
#     assert updated_order_line_object.pallet_no == variables["input"][0]["palletNo"]
#     assert (
#         updated_order_line_object.package_quantity
#         == variables["input"][0]["packageQuantity"]
#     )
#     assert (
#         updated_order_line_object.packing_list == variables["input"][0]["packingList"]
#     )
#     assert (
#         updated_order_line_object.shipping_point
#         == variables["input"][0]["shippingPoint"]
#     )
#     assert (
#         updated_order_line_object.delivery_tol_over
#         == variables["input"][0]["deliveryTolOver"]
#     )
#     assert (
#         updated_order_line_object.delivery_tol_under
#         == variables["input"][0]["deliveryTolUnder"]
#     )
#     assert (
#         updated_order_line_object.delivery_tol_unlimited
#         == variables["input"][0]["deliveryTolUnlimited"]
#     )


# def test_update_order_lines_success(
#     user1_logged, scgp_export_orders, scgp_export_order_lines
# ):
#     order_id = scgp_export_orders[0].id
#     update_line_id = scgp_export_order_lines[0].id
#     variables = {
#         "id": order_id,
#         "input": [
#             {
#                 "id": update_line_id,
#                 "quantity": 9,
#                 "quantityUnit": "Unit2",
#                 "weightUnit": "Weight2",
#                 "itemCatEo": "itemCatEo2",
#                 "plant": "plant2",
#                 "refPiNo": "refPiNo2",
#                 "requestDate": "2022-09-01",
#                 "route": "route2",
#                 "deliveryTolOver": 100.5,
#                 "deliveryTolUnder": 200.5,
#                 "deliveryTolUnlimited": False,
#                 "rollDiameter": 69,
#                 "rollCoreDiameter": 96.5,
#                 "rollQuantity": 100,
#                 "rollPerPallet": 96,
#                 "palletSize": "palletSize2",
#                 "palletNo": "palletNo2",
#                 "packageQuantity": 96.9,
#                 "packingList": "packingList2",
#                 "shippingPoint": "Shipping point2",
#                 "remark": "remark2",
#                 "rejectReason": "NO",
#             }
#         ],
#     }

#     request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
#     with freeze_time(request_time):
#         response = user1_logged.post_graphql(
#             UPDATE_EXPORT_ORDER_LINES_MUTATION, variables
#         )
#     content = get_graphql_content(response)
#     errors = content["data"]["updateExportOrderLines"]["errors"]

#     updated_order_line_object = models.ExportOrderLine.objects.get(id=update_line_id)

#     assert len(errors) == 0
#     assert updated_order_line_object.quantity == variables["input"][0]["quantity"]
#     assert (
#         updated_order_line_object.quantity_unit == variables["input"][0]["quantityUnit"]
#     )
#     assert updated_order_line_object.weight_unit == variables["input"][0]["weightUnit"]
#     assert updated_order_line_object.item_cat_eo == variables["input"][0]["itemCatEo"]
#     assert updated_order_line_object.plant == variables["input"][0]["plant"]
#     assert updated_order_line_object.ref_pi_no == variables["input"][0]["refPiNo"]
#     assert (
#         updated_order_line_object.request_date.strftime("%Y-%m-%d")
#         == variables["input"][0]["requestDate"]
#     )
#     assert updated_order_line_object.route == variables["input"][0]["route"]
#     assert (
#         updated_order_line_object.delivery_tol_over
#         == variables["input"][0]["deliveryTolOver"]
#     )
#     assert (
#         updated_order_line_object.delivery_tol_under
#         == variables["input"][0]["deliveryTolUnder"]
#     )
#     assert (
#         updated_order_line_object.delivery_tol_unlimited
#         == variables["input"][0]["deliveryTolUnlimited"]
#     )
#     assert (
#         updated_order_line_object.roll_diameter == variables["input"][0]["rollDiameter"]
#     )
#     assert (
#         updated_order_line_object.roll_core_diameter
#         == variables["input"][0]["rollCoreDiameter"]
#     )
#     assert (
#         updated_order_line_object.roll_quantity == variables["input"][0]["rollQuantity"]
#     )
#     assert (
#         updated_order_line_object.roll_per_pallet
#         == variables["input"][0]["rollPerPallet"]
#     )
#     assert updated_order_line_object.pallet_size == variables["input"][0]["palletSize"]
#     assert updated_order_line_object.pallet_no == variables["input"][0]["palletNo"]
#     assert (
#         updated_order_line_object.package_quantity
#         == variables["input"][0]["packageQuantity"]
#     )
#     assert (
#         updated_order_line_object.packing_list == variables["input"][0]["packingList"]
#     )
#     assert (
#         updated_order_line_object.shipping_point
#         == variables["input"][0]["shippingPoint"]
#     )
#     assert updated_order_line_object.remark == variables["input"][0]["remark"]
#     assert (
#         updated_order_line_object.net_price
#         == variables["input"][0]["quantity"]
#         * updated_order_line_object.pi_product.price_per_unit
#     )
#     assert (
#         updated_order_line_object.reject_reason
#         == ScgExportRejectReason[variables["input"][0]["rejectReason"]].value
#     )

#     order = models.ExportOrder.objects.get(id=order_id)
#     order_lines = models.ExportOrderLine.objects.filter(order=order).all()

#     total_order_line_net_price = 0
#     for order_line in order_lines:
#         total_order_line_net_price += order_line.net_price

#     assert str(total_order_line_net_price) == order.net_price


def test_update_order_lines_error_order_line_not_exist(
    user1_logged, scgp_export_orders, scgp_export_order_lines
):
    order_id = scgp_export_orders[0].id
    update_line_id = 1234
    variables = {
        "id": order_id,
        "input": [
            {
                "id": update_line_id,
                "quantity": 9,
                "quantityUnit": "Unit2",
                "weightUnit": "Weight2",
                "itemCatEo": "itemCatEo2",
                "plant": "plant2",
                "refPiNo": "refPiNo2",
                "requestDate": "2022-09-01",
                "route": "route2",
                "deliveryTolOver": 100.5,
                "deliveryTolUnder": 200.5,
                "deliveryTolUnlimited": False,
                "rollDiameter": 69,
                "rollCoreDiameter": 96.5,
                "rollQuantity": 100,
                "rollPerPallet": 96,
                "palletSize": "palletSize2",
                "palletNo": "palletNo2",
                "packageQuantity": 96.9,
                "packingList": "packingList2",
                "shippingPoint": "Shipping point2",
                "remark": "remark2",
                "rejectReason": "NO",
            }
        ],
    }

    request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
    with freeze_time(request_time):
        response = user1_logged.post_graphql(
            UPDATE_EXPORT_ORDER_LINES_MUTATION, variables
        )
    content = get_graphql_content(response)
    errors = content["data"]["updateExportOrderLines"]["errors"]
    order = content["data"]["updateExportOrderLines"]["order"]

    assert order is None

    message = f"Order line {update_line_id} don't exist."
    assert errors[0]["message"] == message


def test_update_order_lines_error_request_date(
    user1_logged, scgp_export_orders, scgp_export_order_lines
):
    order_id = scgp_export_orders[0].id
    update_line_id = scgp_export_order_lines[0].id
    variables = {
        "id": order_id,
        "input": [
            {
                "id": update_line_id,
                "quantity": 9,
                "quantityUnit": "Unit2",
                "weightUnit": "Weight2",
                "itemCatEo": "itemCatEo2",
                "plant": "plant2",
                "refPiNo": "refPiNo2",
                "requestDate": "2022-08-01",
                "route": "route2",
                "deliveryTolOver": 100.5,
                "deliveryTolUnder": 200.5,
                "deliveryTolUnlimited": False,
                "rollDiameter": 69,
                "rollCoreDiameter": 96.5,
                "rollQuantity": 100,
                "rollPerPallet": 96,
                "palletSize": "palletSize2",
                "palletNo": "palletNo2",
                "packageQuantity": 96.9,
                "packingList": "packingList2",
                "shippingPoint": "Shipping point2",
                "remark": "remark2",
                "rejectReason": "NO",
            }
        ],
    }
    request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
    with freeze_time(request_time):
        response = user1_logged.post_graphql(
            UPDATE_EXPORT_ORDER_LINES_MUTATION, variables
        )
    content = get_graphql_content(response)
    errors = content["data"]["updateExportOrderLines"]["errors"]
    order = content["data"]["updateExportOrderLines"]["order"]

    message = "Request date must be further than today"

    assert order is None
    assert errors[0]["message"] == message


def test_update_order_lines_error_user_not_login(
    api_client, scgp_export_orders, scgp_export_order_lines
):
    order_id = scgp_export_orders[0].id
    update_line_id = scgp_export_order_lines[0].id
    variables = {
        "id": order_id,
        "input": [
            {
                "id": update_line_id,
                "quantity": 9,
                "quantityUnit": "Unit2",
                "weightUnit": "Weight2",
                "itemCatEo": "itemCatEo2",
                "plant": "plant2",
                "refPiNo": "refPiNo2",
                "requestDate": "2022-08-20",
                "route": "route2",
                "deliveryTolOver": 100.5,
                "deliveryTolUnder": 200.5,
                "deliveryTolUnlimited": False,
                "rollDiameter": 69,
                "rollCoreDiameter": 96.5,
                "rollQuantity": 100,
                "rollPerPallet": 96,
                "palletSize": "palletSize2",
                "palletNo": "palletNo2",
                "packageQuantity": 96.9,
                "packingList": "packingList2",
                "shippingPoint": "Shipping point2",
                "remark": "remark2",
                "rejectReason": "NO",
            }
        ],
    }
    request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
    with freeze_time(request_time):
        response = api_client.post_graphql(
            UPDATE_EXPORT_ORDER_LINES_MUTATION, variables
        )
    message = "You need one of the following permissions: AUTHENTICATED_USER"
    assert_graphql_error_with_message(response, message)


# def test_update_all_order_line_success(
#     user1_logged, scgp_export_orders, scgp_export_order_lines
# ):
#     order_id = scgp_export_orders[0].id
#     variables = {"id": order_id, "input": {"requestDate": "2022-08-20"}}
#     request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
#     with freeze_time(request_time):
#         response = user1_logged.post_graphql(
#             UPDATE_ALL_EXPORT_ORDER_LINES_MUTATION, variables
#         )
#     content = get_graphql_content(response)

#     errors = content["data"]["updateAllExportOrderLine"]["errors"]
#     assert len(errors) == 0

#     order = models.ExportOrder.objects.get(id=order_id)
#     assert order.updated_at == request_time

#     order_lines = models.ExportOrderLine.objects.filter(order__id=order_id)
#     for order_line in order_lines:
#         assert (
#             order_line.request_date.strftime("%Y-%m-%d")
#             == variables["input"]["requestDate"]
#         )


def test_update_all_order_line_error_request_date(
    user1_logged, scgp_export_orders, scgp_export_order_lines
):
    order_id = scgp_export_orders[0].id
    variables = {"id": order_id, "input": {"requestDate": "2022-08-01"}}
    request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
    with freeze_time(request_time):
        response = user1_logged.post_graphql(
            UPDATE_ALL_EXPORT_ORDER_LINES_MUTATION, variables
        )
    content = get_graphql_content(response)

    errors = content["data"]["updateAllExportOrderLine"]["errors"]
    order = content["data"]["updateAllExportOrderLine"]["order"]

    message = "Request date must be further than today"

    assert order is None
    assert errors[0]["message"] == message


def test_update_all_order_line_error_user_not_login(
    api_client, scgp_export_orders, scgp_export_order_lines
):
    order_id = scgp_export_orders[0].id
    variables = {"id": order_id, "input": {"requestDate": "2022-08-01"}}
    request_time = timezone.datetime(2022, 8, 3, 12, 0, 0, tzinfo=UTC)
    with freeze_time(request_time):
        response = api_client.post_graphql(
            UPDATE_ALL_EXPORT_ORDER_LINES_MUTATION, variables
        )
    message = "You need one of the following permissions: AUTHENTICATED_USER"
    assert_graphql_error_with_message(response, message)
