from django.core.exceptions import ValidationError

from scg_checkout.graphql.enums import ScgOrderStatus
from scgp_cip.common.constants import BOM_FLAG_TRUE_VALUE


def validate_order(order):
    if not order:
        raise ValidationError("Order not found!")
    if order.status == ScgOrderStatus.CONFIRMED.value:
        raise ValidationError("Confirmed order can not change status!")


def is_bom_parent(bom_flag, parent):
    bom_flag = (
        bom_flag if isinstance(bom_flag, bool) else BOM_FLAG_TRUE_VALUE == bom_flag
    )
    return bom_flag and not parent


def is_bom_child(bom_flag, parent):
    bom_flag = (
        bom_flag if isinstance(bom_flag, bool) else BOM_FLAG_TRUE_VALUE == bom_flag
    )
    return bom_flag and parent


def prepare_otc_partner_address_update(otc_info, partner_address):
    partner_address.name1 = otc_info.get("name1")
    partner_address.name2 = otc_info.get("name2")
    partner_address.name3 = otc_info.get("name3")
    partner_address.name4 = otc_info.get("name4")
    partner_address.city = otc_info.get("city")
    partner_address.postal_code = otc_info.get("postal_code")
    partner_address.district = otc_info.get("district")
    partner_address.street_1 = otc_info.get("street_1")
    partner_address.street_2 = otc_info.get("street_2")
    partner_address.street_3 = otc_info.get("street_3")
    partner_address.street_4 = otc_info.get("street_4")
    partner_address.location = otc_info.get("location")
    partner_address.transport_zone_code = otc_info.get("transport_zone_code")
    partner_address.transport_zone_name = otc_info.get("transport_zone_name")
    partner_address.country_code = otc_info.get("country_code")
    partner_address.country_name = otc_info.get("country_name")
    partner_address.telephone_no = otc_info.get("telephone_no")
    partner_address.telephone_extension = otc_info.get("telephone_extension")
    partner_address.mobile_no = otc_info.get("mobile_no")
    partner_address.fax_no = otc_info.get("fax_no")
    partner_address.fax_no_ext = otc_info.get("fax_no_ext")
    partner_address.email = otc_info.get("email")
    partner_address.language = otc_info.get("language")
    partner_address.tax_number1 = otc_info.get("tax_number1")
    partner_address.tax_number2 = otc_info.get("tax_number2")
    partner_address.tax_id = otc_info.get("tax_id")
    partner_address.branch_id = otc_info.get("branch_id")
    return partner_address


def separate_parent_and_bom_order_lines(order_lines):
    parent_and_normal_order_line_list = []
    bom_child_list = []
    for order_lines in order_lines:
        if order_lines["parent_item_no"] == "":
            parent_and_normal_order_line_list.append(order_lines)
        else:
            bom_child_list.append(order_lines)
    return bom_child_list, parent_and_normal_order_line_list


def sorted_and_merged_order_line_list(
    reverse, sorted_bom_child_list, sorted_parent_and_normal_order_line_list
):
    sorted_list = []
    index = 0
    while index < len(sorted_parent_and_normal_order_line_list):
        if not reverse:
            sorted_list.append(sorted_parent_and_normal_order_line_list[index])

        if (
            "bom_flag" in sorted_parent_and_normal_order_line_list[index]
            and sorted_parent_and_normal_order_line_list[index]["bom_flag"] == True
        ):
            bom_child_filter_list = [
                item
                for item in sorted_bom_child_list
                if int(item.get("parent_item_no", 0))
                == int(
                    sorted_parent_and_normal_order_line_list[index].get("item_no", 0)
                )
                and (
                    int(item.get("order_no", 0))
                    == int(
                        sorted_parent_and_normal_order_line_list[index].get(
                            "order_no", 0
                        )
                    )
                )
            ]
            sorted_list.extend(bom_child_filter_list)

        if reverse:
            sorted_list.append(sorted_parent_and_normal_order_line_list[index])

        index += 1
    return sorted_list
