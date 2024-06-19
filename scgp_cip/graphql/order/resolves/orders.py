from scg_checkout.graphql.resolves.orders import get_address_from_code
from scgp_cip.dao.order.order_repo import OrderRepo
from scgp_cip.dao.order_line.order_line_repo import OrderLineRepo
from scgp_cip.dao.order_line_cp.order_line_cp_repo import OrderLineCpRepo
from scgp_cip.service.helper.order_line_helper import is_bom_child
from scgp_cip.service.helper.preview_order_helper import generate_order_header_res, generate_order_item_res, \
    generate_order_footer_res, calculate_price_weight_for_parent_bom_mat
from scg_checkout.graphql.helper import mapping_order_partners
from scgp_cip.service.integration.integration_service import get_order_details


def resolve_get_order_data(info, order_id):
    return OrderRepo.get_order_by_id(order_id)


def resolve_sold_to_address(root, info):
    try:
        sold_to_code = root.sold_to.sold_to_code
        sold_to_address = get_address_from_code(sold_to_code)
        if sold_to_address:
            return sold_to_address
        return sold_to_code
    except Exception:
        return sold_to_code


def resolve_preview_domestic_page_order(info, order_id):

    order = OrderRepo.get_order_by_id_or_so_no(order_id)
    if not order:
        raise ValueError(f"Invalid order Id {order_id} ")
    es26_response = get_order_details(so_no=order.so_no)

    order_lines_db = OrderLineRepo.find_all_order_line_by_order(order)
    order_line_ids = [order_line.id for order_line in order_lines_db]
    order_line_cps = OrderLineCpRepo.get_order_lines_cp_by_order_line_ids(order_line_ids)
    order_line_id_order_line_cp = {line.order_line_id: line for line in order_line_cps}
    item_no_order_line_db = {line.item_no: line for line in order_lines_db}
    order_header_from_es_26 = es26_response["data"][0]["orderHeaderIn"]
    if not order_header_from_es_26:
        return
    order_partners_from_es26 = es26_response["data"][0]["orderPartners"]
    order_lines_from_es26 = es26_response["data"][0].get("orderItems", [])
    sold_to_code = order.sold_to.sold_to_code
    order_partners = mapping_order_partners(order_partners_from_es26)
    order_header_res = generate_order_header_res(order, order_header_from_es_26, order_partners, sold_to_code)
    order_items_res = []
    parent_item_no_child_dict = {}
    for order_line_from_es in order_lines_from_es26:
        item_no = order_line_from_es.get("itemNo").lstrip("0")
        order_line_db = item_no_order_line_db.get(item_no)
        parent_item_no = order_line_from_es.get("parentItemNo", "").lstrip("0")
        order_item = generate_order_item_res(item_no, order_line_db, order_line_from_es, order_line_id_order_line_cp,
                                             parent_item_no, order_header_from_es_26)
        if is_bom_child(order_line_from_es.get("bomFlag", "") , parent_item_no):
            parent_item_no_child_dict.setdefault(parent_item_no, []).append(order_item)
        order_items_res.append(order_item)
    sorted_order_items = sorted(order_items_res, key=lambda x: int(x["item_no"]))
    calculate_price_weight_for_parent_bom_mat(order_items_res, parent_item_no_child_dict, order_line_id_order_line_cp)
    order_footer_res = generate_order_footer_res(order_header_from_es_26)
    response = {"preview_header_data": order_header_res, "preview_item_data": sorted_order_items,
                "preview_footer_data": order_footer_res}
    return response
