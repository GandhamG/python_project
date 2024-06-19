import pytz

from scg_checkout.graphql.implementations.iplan import get_sold_to_no_name
from scgp_cip.common.constants import BOM_FLAG_TRUE_VALUE
from scgp_cip.dao.order_line.material_sale_master_repo import MaterialSaleMasterRepo
from scgp_cip.service.helper.order_helper import get_line_status_from_es26_cip


def generate_order_header_res(
    order, order_header_from_es_26, order_partners, sold_to_code
):
    return {
        "so_no": order_header_from_es_26.get("saleDocument"),
        "po_number": order_header_from_es_26.get("poNo"),
        "order_date": order_header_from_es_26.get("createDate"),
        "payment_term": order_header_from_es_26.get("paymentTerms"),
        "sale_organization": order.sales_organization,
        "ship_to": order_partners["order"].get("ship_to"),
        "bill_to": order_partners["order"].get("bill_to"),
        "sale_employee": order.sales_employee,
        "customer_name": f"{sold_to_code} {get_sold_to_no_name(sold_to_code, return_only_name=True)}",
        "order_type": order_header_from_es_26.get("docType"),
        "remark": order.orderextension.additional_txt_header_note1
        if order.orderextension
        else "",
        "record_date": convert_date_time_to_timezone_asia(order.saved_sap_at),
        "order_created_by": order.created_by if order.created_by else "",
    }


def generate_order_item_res(
    item_no,
    order_line_db,
    order_line_from_es,
    order_line_id_order_line_cp,
    parent_item_no,
    order_header_from_es_26,
):
    sale_text_1 = (
        order_line_from_es.get("saleText1_th")
        if order_line_from_es.get("saleText1_th")
        else ""
    )
    sale_text_2 = (
        order_line_from_es.get("saleText2_th")
        if order_line_from_es.get("saleText2_th")
        else ""
    )
    sale_text_3 = (
        order_line_from_es.get("saleText3_th")
        if order_line_from_es.get("saleText3_th")
        else ""
    )
    sale_text_4 = (
        order_line_from_es.get("saleText4_th")
        if order_line_from_es.get("saleText4_th")
        else ""
    )
    order_item = {
        "item_no": item_no,
        "material_code": order_line_from_es.get("material"),
        "material_description": order_line_from_es.get("materialDesc"),
        "quantity": order_line_from_es.get("orderQty"),
        "sales_unit": order_line_from_es.get("salesUnit"),
        "weight": order_line_from_es.get("netWeight"),
        "weight_unit": order_line_from_es.get("weightUnit"),
        "price_per_unit": order_line_from_es.get("netPricePerUnit"),
        "formatted_price_per_unit": "{:,.2f}".format(
            order_line_from_es.get("netPricePerUnit")
        )
        if order_line_from_es.get("netPricePerUnit")
        else 0,
        "net_price": order_line_from_es.get("totalNetPrice"),
        "formatted_net_price": "{:,.2f}".format(order_line_from_es.get("totalNetPrice"))
        if order_line_from_es.get("totalNetPrice")
        else 0,
        "request_date": order_line_from_es.get("requestedDate"),
        "bom_flag": order_line_from_es.get("bomFlag"),
        "material_desc": f"{sale_text_1}\n{sale_text_2}\n{sale_text_3}\n{sale_text_4}",
        "parent_item_no": parent_item_no,
        "reason_reject": order_line_from_es.get("reasonReject", None),
        "original_request_date": order_line_db
        and order_line_db.original_request_date
        and order_line_db.original_request_date.strftime("%d/%m/%Y"),
    }
    item_status_count_dict = {
        "cancelled_item_count": 0,
        "completed_item_count": 0,
        "partial_deliver_item_count": 0,
    }
    order_item.update(
        get_line_status_from_es26_cip(order_line_from_es, item_status_count_dict)
    )
    material_sale_master = (
        MaterialSaleMasterRepo.get_material_sale_master_by_material_code(
            order_item.get("material_code"),
            order_header_from_es_26.get("salesOrg"),
            order_header_from_es_26.get("distributionChannel"),
        )
    )
    if material_sale_master:
        order_item.update({"plant": material_sale_master.delivery_plant})
    if order_line_db:
        order_item.update({"id": order_line_db.id})
        order_line_cp = order_line_id_order_line_cp.get(order_line_db.id)
        if order_line_cp:
            order_item.update(
                {
                    "confirmed_date": order_line_cp.confirm_date,
                    "confirmed_plant": order_line_cp.plant,
                }
            )
    return order_item


def generate_order_footer_res(order_header_from_es_26):
    order_footer_res = {
        "net_total_price": order_header_from_es_26.get("orderAmtBeforeVat"),
        "total_vat": order_header_from_es_26.get("orderAmtVat"),
        "order_amount_after_vat": order_header_from_es_26.get("orderAmtAfterVat"),
        "currency": order_header_from_es_26.get("currency"),
        "formatted_net_total_price": f"{order_header_from_es_26.get('orderAmtBeforeVat'):,.2f}",
        "formatted_total_vat": f"{order_header_from_es_26.get('orderAmtVat'):,.2f}",
        "formatted_order_amount_after_vat": f"{order_header_from_es_26.get('orderAmtAfterVat'):,.2f}",
    }
    return order_footer_res


def calculate_price_weight_for_parent_bom_mat(
    order_items_res, parent_item_no_child_dict, order_line_id_order_line_cp
):
    for order_item_res in order_items_res:
        if BOM_FLAG_TRUE_VALUE == order_item_res.get(
            "bom_flag"
        ) and not order_item_res.get("parent_item_no"):
            child_lines = parent_item_no_child_dict.get(order_item_res.get("item_no"))
            if child_lines:
                parent_weight = 0
                net_price = 0
                for child_line in child_lines:
                    parent_weight += child_line.get("weight", 0)
                    net_price += child_line.get("net_price", 0)
                order_line_cp = order_line_id_order_line_cp.get(
                    child_lines[0].get("id")
                )
                if order_line_cp:
                    order_item_res.update(
                        {
                            "confirmed_date": order_line_cp.confirm_date,
                            "confirmed_plant": order_line_cp.plant,
                        }
                    )
                order_item_res["weight"] = parent_weight
                order_item_res["price_per_unit"] = net_price / order_item_res.get(
                    "quantity", 1
                )
                order_item_res["net_price"] = net_price
                order_item_res["formatted_price_per_unit"] = "{:,.2f}".format(
                    order_item_res["price_per_unit"]
                )
                order_item_res["formatted_net_price"] = "{:,.2f}".format(
                    order_item_res["net_price"]
                )


def populate_bill_to_and_ship_to(bill_to, ship_to, order_header_data):
    bill_to_split = bill_to and bill_to.split("\n")
    ship_to_split = ship_to and ship_to.split("\n")
    order_header_data["bill_to_name"] = bill_to_split and bill_to_split[0] or ""
    order_header_data["bill_to_name"] = order_header_data["bill_to_name"].replace(
        "-", " ", 1
    )
    order_header_data["bill_to_address"] = (
        bill_to_split[1] if bill_to_split and len(bill_to_split) == 2 else ""
    )
    order_header_data["ship_to_name"] = ship_to_split and ship_to_split[0] or ""
    order_header_data["ship_to_name"] = order_header_data["ship_to_name"].replace(
        "-", " ", 1
    )
    order_header_data["ship_to_address"] = (
        ship_to_split[1] if ship_to_split and len(ship_to_split) == 2 else ""
    )


def convert_date_time_to_timezone_asia(date_time):
    if date_time:
        return date_time.astimezone(pytz.timezone("Asia/Bangkok")).strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    else:
        return ""
