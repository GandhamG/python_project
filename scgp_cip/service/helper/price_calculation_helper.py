import uuid

from scg_checkout.graphql.helper import round_qty_decimal
from scg_checkout.graphql.types import SapItemMessage, SapOrderMessage
from scg_checkout.graphql.validators import validate_positive_decimal
from scgp_cip.common.constants import DMY_FORMAT, SCHEDULE_LINE, YMD_FORMAT
from scgp_cip.common.enum import MaterialTypes
from scgp_cip.common.helper.date_time_helper import convert_date_format
from scgp_cip.common.helper.helper import add_key_and_data_into_params
from scgp_cip.service.helper.create_order_helper import fetch_item_category


def prepare_payload_for_es_41(
    lines_in,
    order_db,
    order_information_in,
    order_partners,
    item_no_order_line_db,
):
    request_date_in = convert_date_format(
        order_information_in.request_date, YMD_FORMAT, DMY_FORMAT
    )
    body = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order_information_in.get("so_no", ""),
        "orderHeaderIn": {
            "docType": order_information_in.order_type,
            "salesOrg": order_db.sales_organization
            and order_db.sales_organization.code
            or "",
            "distributionChannel": order_db.distribution_channel
            and order_db.distribution_channel.code
            or "",
            "division": order_db.division and order_db.division.code or "",
            "requestDate": request_date_in,
            "priceDate": convert_date_format(
                order_information_in.request_date, YMD_FORMAT, DMY_FORMAT
            ),
            "taxClass": str(order_information_in.get("tax_class_id", "")),
        },
        "orderPartners": order_partners,
    }
    add_key_and_data_into_params("currency", order_information_in.currency, body)
    order_items_in = []
    order_schedules_in = []
    for line_in in lines_in:
        order_line_db = item_no_order_line_db.get(line_in["item_no"])
        quantity = line_in.quantity
        validate_positive_decimal(quantity, "Quantity")
        quantity_in = round_qty_decimal(quantity)
        line_item_no = line_in.item_no.zfill(6)
        order_item_in = {
            "itemNo": line_item_no,
            "material": line_in.material_no,
            "targetQuantity": quantity_in,
            "salesUnit": line_in.sale_unit,
            "itemCategory": fetch_item_category(
                order_line_db.material,
                order_information_in.order_type,
                line_in.get("production_flag", ""),
                line_in.get("batch_no", ""),
            )
            if order_line_db
            else "",
            "priceDate": convert_date_format(
                line_in.price_date,
                YMD_FORMAT,
                DMY_FORMAT,
            ),
        }
        if line_in.get("reject_reason"):
            order_item_in["rejectReason"] = line_in.get("reject_reason")
        add_key_and_data_into_params(
            "custMat35", line_in.get("cust_mat_code", ""), order_item_in
        )

        if line_in.get("plant", ""):
            order_item_in["plant"] = line_in.get("plant")
        elif (
            order_line_db
            and order_line_db.material.material_type
            == MaterialTypes.SERVICE_MATERIAL.value
            and order_line_db.plant
        ):
            order_item_in["plant"] = order_line_db.plant

        if (
            order_line_db
            and order_line_db.bom_flag
            and order_line_db.parent
            and line_in.get("parent_item_no", "")
        ):
            order_item_in["parentItemNo"] = line_in.get("parent_item_no").zfill(6)

        order_schedule_in = {
            "itemNo": line_item_no,
            "requestDate": convert_date_format(
                line_in.request_date,
                YMD_FORMAT,
                DMY_FORMAT,
            ),
            "requestQuantity": quantity_in,
        }
        if order_information_in.get("so_no", ""):
            order_schedule_in["scheduleLine"] = SCHEDULE_LINE
        order_schedules_in.append(order_schedule_in)
        order_items_in.append(order_item_in)
    body["orderItemsIn"] = order_items_in
    body["orderSchedulesIn"] = order_schedules_in
    return body


def get_response_message(response, success, sap_order_messages, sap_item_messages):
    response.success = success

    # Return SAP message for order and item in price calculation
    if len(sap_order_messages):
        response.sap_order_messages = []
        for sap_order_message in sap_order_messages:
            response.sap_order_messages.append(
                SapOrderMessage(
                    error_code=sap_order_message.get("error_code"),
                    so_no=sap_order_message.get("so_no"),
                    error_message=sap_order_message.get("error_message"),
                )
            )
    if len(sap_item_messages):
        response.sap_item_messages = []
        for sap_item_message in sap_item_messages:
            response.sap_item_messages.append(
                SapItemMessage(
                    item_status=sap_item_message.get("error_code"),
                    item_no=sap_item_message.get("item_no"),
                    message=sap_item_message.get("error_message"),
                )
            )
    return response
