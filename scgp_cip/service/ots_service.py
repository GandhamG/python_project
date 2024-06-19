from common.ots.ots_api import OTSApiRequest
from scgp_cip.service.helper.order_helper import prepare_payload_ots


def prepare_payload_and_call_ots(input_data, info):
    params = prepare_payload_ots(input_data, info)
    ots_response = OTSApiRequest.call_ots_get_data(params)
    return ots_response.get("data") if ots_response.get("data") else []


def extract_and_map_ots_response_to_sap_response(sap_response, ots_response):
    if not sap_response:
        return
    so_no_item_details_dict = {}
    if ots_response:
        for item in ots_response:
            item_dict = so_no_item_details_dict.setdefault(item.get("salesOrderNo"), {})
            item_dict[item.get("itemNo").lstrip("0")] = item

    for sap_order_line in sap_response:
        so_no = sap_order_line.get("sdDoc", "")
        ots_order_line_dict = so_no_item_details_dict.get(so_no, {})
        item_no = sap_order_line.get("itemNo", "").lstrip("0")
        if ots_order_line_dict.get(item_no):
            ots_order_line = ots_order_line_dict.get(item_no)
            sap_order_line["giQty"] = ots_order_line.get("deliveryQty")
            sap_order_line["pendingGiQty"] = ots_order_line.get("pendingQty")
            sap_order_line["confirmQty"] = ots_order_line.get("confirmQty")
            sap_order_line["nonConfirmQty"] = ots_order_line.get("pendingQty")
            sap_order_line["trackingStatus"] = ots_order_line.get("trackingStatus", "")
            sap_order_line["URL"] = ots_order_line.get("url", "")
        else:
            sap_order_line["giQty"] = None
            sap_order_line["pendingGiQty"] = None
            sap_order_line["confirmQty"] = None
            sap_order_line["nonConfirmQty"] = None
