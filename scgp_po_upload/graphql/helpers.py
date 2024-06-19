import json

from django.template.loader import get_template

from scg_checkout.graphql.implementations.weasyprint_custom import PdfGenerator
from scgp_po_upload.graphql.enums import IPlanAcknowledge, MessageErrorItem, BeingProcessConstants
from sap_master_data.models import Conversion2Master


def html_to_pdf(context_dict, header_html, content_html, mt="-90mm", mr="-10mm", orientation="portrait"):
    remark = context_dict.get("remark_order_info", "")
    if remark:
        context_dict["remark_order_info"] = remark.splitlines()
    else:
        context_dict["remark_order_info"] = None
    header = get_template(header_html)
    header_render = header.render(context_dict)
    body = get_template(content_html)
    body_render = body.render(context_dict)
    pdf = PdfGenerator(main_html=body_render, header_html=header_render, mt=mt, mr=mr, orientation=orientation)
    return pdf.render_pdf()


def html_to_pdf_order_confirmation(context_dict, header_html, content_html, footer_html, mt="-80mm", mr="-10mm",
                                   orientation="portrait"):
    remark = context_dict.get("remark_order_info", "")
    context_dict["remark_order_info"] = None
    if remark:
        context_dict["remark_order_info"] = remark.splitlines()


    header = get_template(header_html)
    header_render = header.render(context_dict)
    body = get_template(content_html)
    body_render = body.render(context_dict)
    footer = get_template(footer_html)
    footer_render = footer.render(context_dict)
    pdf = PdfGenerator(main_html=body_render, header_html=header_render, mt=mt, mr=mr, orientation=orientation,
                       footer_html=footer_render)
    return pdf.render_pdf()


def get_i_plan_error_messages(i_plan_response):
    i_plan_error_messages = []
    is_change_flow = False
    if i_plan_response.get("DDQResponse"):
        response_lines = i_plan_response.get("DDQResponse").get("DDQResponseHeader")[0].get("DDQResponseLine")
    elif i_plan_response.get("DDQAcknowledge"):
        response_lines = i_plan_response.get("DDQAcknowledge").get("DDQAcknowledgeHeader")[0].get("DDQAcknowledgeLine")
    elif i_plan_response.get("OrderUpdateResponse").get("OrderUpdateResponseLine"):
        response_lines = i_plan_response.get("OrderUpdateResponse").get("OrderUpdateResponseLine")
        is_change_flow = True
    else:
        return []

    for line in response_lines:
        if line.get("returnStatus").lower() == IPlanAcknowledge.FAILURE.value.lower():
            if is_change_flow:
                return_code = line.get("returnCode", "1")
                i_plan_error_messages.append({
                    "item_no": line.get("lineCode", "").lstrip("0"),
                    "first_code": return_code,
                    "second_code": "",
                    "message": line.get("returnCodeDescription"),
                })
            else:
                return_code = line.get("returnCode")
                i_plan_error_messages.append({
                    "item_no": line.get("lineNumber", "").lstrip("0"),
                    "first_code": return_code and return_code[18:24] or "0",
                    "second_code": return_code and return_code[24:32] or "0",
                    "message": line.get("returnCodeDescription"),
                })

    return i_plan_error_messages


def load_error_message():
    f = open("scgp_po_upload/implementations/error_messages_order_header.json")
    data = json.load(f)
    return data


def format_order_header_msg(order_header_response, error_msg_order_header):
    msg_id = order_header_response.get("id")
    msg_number = order_header_response.get("number")
    message_format = error_msg_order_header.get(msg_id, {}).get(msg_number, None)
    if message_format:
        order_header_msg = f"{msg_id} {msg_number} {message_format}"
        message_v1 = order_header_response.get("messageV1", "")
        message_v2 = order_header_response.get("messageV2", "")
        message_v3 = order_header_response.get("messageV3", "")
        message_v4 = order_header_response.get("messageV4", "")
        order_header_msg = order_header_msg.replace("&1", message_v1)
        order_header_msg = order_header_msg.replace("&2", message_v2)
        order_header_msg = order_header_msg.replace("&3", message_v3)
        order_header_msg = order_header_msg.replace("&4", message_v4)
        if "&" in order_header_msg:
            message_list = [message_v1, message_v2, message_v3, message_v4]
            for message in message_list:
                order_header_msg = order_header_msg.replace("&", message, 1)
    else:
        order_header_msg = f"{msg_id} {msg_number} {order_header_response.get('message')}"
    return order_header_msg


def get_item_level_message(
        order_item_message,
        i_plan_request_error_message,
        i_plan_confirm_error_message,
        order_line,
):
    item_no = order_line.item_no
    i_plan_request_error_message = i_plan_request_error_message or []
    i_plan_confirm_error_message = i_plan_confirm_error_message or []
    msg = [
        item.get("message")
        for item in i_plan_request_error_message + i_plan_confirm_error_message
        if item.get("item_no") == item_no
    ]
    for item in order_item_message:
        if item == item_no:
            msg += [order_item_message[item]]
            break

    return "\n".join(msg) if len(msg) > 0 else ""


def error_msg_when_order_is_being_process(data):
    return f"{data.get('id')} {data.get('number')} {data.get('message')}"


def validate_order_msg(data, error_msg_order_header, order_header_msg):
    if data.get("id").startswith("V"):
        message = format_order_header_msg(data, error_msg_order_header)
        order_header_msg.append(message)
    return order_header_msg

def convert_qty_ton_by_sales_unit(quantity, material_code, sales_unit):
    try:
        if material_code is not None:
            conversion = Conversion2Master.objects.filter(
                material_code=material_code, to_unit=sales_unit
            ).last()
            calculation = conversion.calculation
            quantity_ton = float(quantity) * float(calculation) / 1000
            return f"{quantity_ton:.3f}"
        else:
            raise TypeError(f"material_code is {material_code}")
    except Exception:
        return ""
