from scgp_cip.common.constants import DMY_FORMAT, PMT_API_LAST_UPDATED_DATE_FORMAT
from scgp_cip.common.helper.date_time_helper import convert_date_format
from scgp_cip.common.helper.helper import add_key_and_data_into_params

PMT_MAT_SEARCH_API_DEFAULT_ROLE = "4"


def prepare_param_for_pmt_mat_search(filter_input):
    params = {
        "Role": PMT_MAT_SEARCH_API_DEFAULT_ROLE,
    }

    add_key_and_data_into_params("pc1", filter_input.get("pc_1", ""), params)
    add_key_and_data_into_params("pc2", filter_input.get("pc_2", ""), params)
    add_key_and_data_into_params("pc3", filter_input.get("pc_3", ""), params)
    add_key_and_data_into_params("pc4", filter_input.get("pc_4", ""), params)
    add_key_and_data_into_params("pc5", filter_input.get("pc_5", ""), params)
    add_key_and_data_into_params("pc6", filter_input.get("pc_6", ""), params)
    add_key_and_data_into_params("partNo", filter_input.get("part_no", ""), params)
    add_key_and_data_into_params("custId", filter_input.get("cust_id", ""), params)
    add_key_and_data_into_params("custName", filter_input.get("cust_name", ""), params)
    add_key_and_data_into_params("desc", filter_input.get("description", ""), params)
    add_key_and_data_into_params("saleText", filter_input.get("sale_text", ""), params)
    add_key_and_data_into_params("wid", filter_input.get("mat_width", None), params)
    add_key_and_data_into_params("leg", filter_input.get("mat_length", None), params)
    add_key_and_data_into_params("hig", filter_input.get("mat_height", None), params)
    return params


def formatted_pmt_api_response(response):
    result = []
    for data in response:
        row = {
            "stock_fg": data.get("stockFG", ""),
            "stock_qa": data.get("stockQA", ""),
            "stock_wip": data.get("stockWIP", ""),
            "hold": data.get("hold", ""),
            "cust_name": data.get("custName", ""),
            "cust_id": data.get("cusId", ""),
            "cust_code": data.get("custCode", ""),
            "pc": data.get("pc", ""),
            "material_no": data.get("materialNo", ""),
            "part_no": data.get("partNo", ""),
            "description": data.get("description", ""),
            "sale_text": data.get("saleText", ""),
            "rate": data.get("rate", None),
            "flute": data.get("flute", ""),
            "board": data.get("board", ""),
            "width": data.get("wid", None),
            "length": data.get("leg", None),
            "height": data.get("hig", None),
            "vendor_name": data.get("vendorName", ""),
            "net_price": data.get("netPrice", ""),
            "pur_txt": data.get("purTxt", ""),
            "remark": data.get("remark", ""),
            "weight_box": data.get("weightBox", None),
            "plant": data.get("plant", ""),
            "sale_org": data.get("saleOrg", ""),
            "last_update": convert_date_format(
                data.get("lastUpdate", ""),
                PMT_API_LAST_UPDATED_DATE_FORMAT,
                DMY_FORMAT,
            ),
            "hold_remark": data.get("holdRemark", ""),
        }
        if row:
            result.append(row)
    return result
