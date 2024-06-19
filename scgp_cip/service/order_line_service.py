import copy
import logging
from datetime import datetime

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.utils import timezone

from common.cp.cp_helper import filter_cp_order_line, is_cp_planning_required
from common.cp.cp_service import prepare_cp_order_line_using_cp_item_messages
from common.enum import EorderingItemStatusEN, EorderingItemStatusTH
from sap_migration import models as sap_migration_models
from sap_migration.graphql.enums import OrderType
from sap_migration.models import OrderLines, OrderOtcPartnerAddress
from scg_checkout.graphql.enums import (
    OrderLineStatus,
    RealtimePartnerType,
    ScgOrderStatusSAP,
)
from scg_checkout.graphql.helper import update_order_status
from scgp_cip.common.constants import (
    BOM_ITEM_CATEGORY_GROUP,
    DMY_FORMAT,
    REASON_REJECT,
    YMD_FORMAT,
)
from scgp_cip.common.enum import (
    CIPOrderItemStatus,
    CIPOrderPaymentType,
    CPRequestType,
    MaterialTypes,
    ProductionFlag,
)
from scgp_cip.dao.order.order_otc_partner_address_repo import OrderOtcPartnerAddressRepo
from scgp_cip.dao.order.order_repo import OrderRepo
from scgp_cip.dao.order.sold_to_master_repo import SoldToMasterRepo
from scgp_cip.dao.order_line.bom_material_repo import BomMaterialRepo
from scgp_cip.dao.order_line.conversion2master_repo import Conversion2MasterRepo
from scgp_cip.dao.order_line.material_master_repo import MaterialMasterRepo
from scgp_cip.dao.order_line.material_sale_master_repo import MaterialSaleMasterRepo
from scgp_cip.dao.order_line.order_line_repo import OrderLineRepo
from scgp_cip.dao.order_line.sold_to_channel_master_repo import SoldToChannelMasterRepo
from scgp_cip.dao.order_line.sold_to_material_master_repo import (
    SoldToMaterialMasterRepo,
)
from scgp_cip.dao.order_line_cp.order_line_cp_repo import OrderLineCpRepo
from scgp_cip.service.change_order_service import (
    change_order_update,
    prepare_params_for_es18_undo,
    process_change_order_split_es_18,
)
from scgp_cip.service.helper.order_line_helper import (
    is_bom_parent,
    prepare_otc_partner_address_update,
    validate_order,
)
from scgp_cip.service.helper.update_order_helper import (
    prepare_params_for_cancel_delete_es18,
)
from scgp_export.implementations.iplan import handle_case_being_process_sap


@transaction.atomic
def delete_order_lines(ids):
    try:
        order_lines_to_delete = OrderLineRepo.get_order_lines(ids)
        if not order_lines_to_delete:
            raise ValidationError("order_line not found!")
        order_id = order_lines_to_delete.first().order_id
        delete_bom_child(order_lines_to_delete)
        result = OrderLineRepo.delete_order_lines(order_lines_to_delete)
        update_order_lines_item_no(order_id)
        return result
    except Exception as e:
        transaction.set_rollback(True)
        if isinstance(e, ValidationError):
            raise e
        raise ImproperlyConfigured(e)


@transaction.atomic
def add_order_line(request):
    try:
        order_line_id = request.get("id", None)
        created_order_lines = create_order_line(request)
        if order_line_id:
            return update_order_line(order_line_id, created_order_lines)
        new_item_no = OrderLineRepo.get_latest_item_no(request.get("order_id")) + 10
        update_item_no(created_order_lines, new_item_no)
        return created_order_lines, False
    except Exception as e:
        transaction.set_rollback(True)
        if isinstance(e, ValidationError):
            raise e
        raise ImproperlyConfigured(e)


def update_item_no(order_lines, item_no):
    for item in order_lines:
        item.item_no = item_no
        item_no += 10
    OrderLineRepo.update_order_line_bulk(order_lines, ["item_no"])
    return item_no


def delete_bom_child(order_lines_to_delete):
    parent_ids = [
        item.id for item in order_lines_to_delete if is_bom_parent(item, item.parent)
    ]
    if parent_ids:
        OrderLineRepo.delete_bom_order_lines_by_parent_id(parent_ids)


def create_order_line(request):
    order_id = request.get("order_id")
    material_code = request.get("material_code")
    order = OrderRepo.get_order_by_id(order_id)
    validate_order(order)
    sold_to_channel_master = get_sold_to_channel_master(order)
    order_line = construct_order_line_object(
        material_code, order, sold_to_channel_master
    )
    # check whether material is BOM or not
    order_lines = [order_line]
    if order_line.bom_flag:
        OrderLineRepo.save_order_line(order_line)
        # fetch BOM child materials
        bom_order_lines = get_bom_order_lines(
            order_line,
            order,
            sold_to_channel_master,
        )
        OrderLineRepo.save_order_lines(bom_order_lines)
        order_lines.extend(bom_order_lines)
        return order_lines
    OrderLineRepo.save_order_line(order_line)
    return order_lines


def update_order_line(order_line_id, created_order_lines):
    order_line_to_delete = OrderLineRepo.get_order_line(order_line_id)
    if not order_line_to_delete:
        raise ValidationError("order_line not found!")
    item_no = int(order_line_to_delete.item_no)
    order_id = order_line_to_delete.order_id
    deleted_items_count = OrderLineRepo.delete_order_lines(order_line_to_delete)
    if is_bom_parent(order_line_to_delete.bom_flag, order_line_to_delete.parent):
        deleted_items_count += OrderLineRepo.delete_bom_order_lines_by_parent_id(
            [order_line_to_delete.id]
        )
    latest_item_no = OrderLineRepo.get_latest_item_no(order_id)
    last_item_deleted = latest_item_no < item_no
    order_lines_to_update = list(
        OrderLineRepo.get_order_line_gt_item_no(order_id, item_no)
    )
    item_no = update_item_no(created_order_lines, item_no)
    if len(created_order_lines) == deleted_items_count or last_item_deleted:
        return created_order_lines, False
    update_item_no(order_lines_to_update, item_no)
    return created_order_lines, True


def update_order_lines_item_no(order_id):
    order_lines = OrderLineRepo.get_order_lines_by_order_id_without_split(order_id)
    order_lines_to_update = []
    item_no = 10
    for order_line in order_lines:
        order_line.item_no = item_no
        order_lines_to_update.append(order_line)
        item_no += 10
    OrderLineRepo.update_order_lines(order_lines, order_lines_to_update, ["item_no"])


def get_sold_to_channel_master(order):
    sold_to_code = order.sold_to.sold_to_code
    sales_org = order.sales_organization.code
    distribution_channel = order.distribution_channel.code
    return SoldToChannelMasterRepo.get_sold_to_channel_master_by_sales_info(
        sold_to_code, sales_org, distribution_channel
    )


def construct_order_line_object(material_code, order, sold_to_channel_master):
    product_material = MaterialMasterRepo.get_material_by_material_code(material_code)
    if not product_material:
        raise ValidationError("Material not found in SAP Master")
    material_sale_master = (
        MaterialSaleMasterRepo.get_material_sale_master_by_material_code(
            material_code,
            order.sales_organization.code,
            order.distribution_channel.code,
        )
    )
    if not material_sale_master:
        raise ValidationError("Material not found in sale master")
    plant_code = (
        material_sale_master.delivery_plant
        if MaterialTypes.SERVICE_MATERIAL.value == product_material.material_type
        else None
    )
    sales_unit = material_sale_master.sales_unit or product_material.base_unit
    sold_to_material = SoldToMaterialMasterRepo.get_sold_to_material_by_material_code(
        material_code
    )
    conversion_master = (
        Conversion2MasterRepo.get_conversion_by_material_code_and_tounit(
            material_code, sales_unit
        )
    )
    language = SoldToMasterRepo.get_sold_to_data(order.sold_to.sold_to_code).language
    order_line = sap_migration_models.OrderLines(
        order_id=order.id,
        material_id=product_material.id,
        material_code=material_code,
        customer_mat_35=sold_to_material.sold_to_material_code
        if sold_to_material
        else None,
        production_flag=ProductionFlag.PRODUCED.value,
        payment_term_item=order.payment_term,
        sales_unit=sales_unit,
        plant=plant_code,
        type=OrderType.DOMESTIC.value,
        prc_group_1=material_sale_master.material_group1,
        request_date=order.request_date,
        weight_unit=conversion_master and conversion_master.from_unit or sales_unit,
        weight=conversion_master and conversion_master.calculation or 1,
        sale_text1=material_sale_master.sale_text1_en
        if language == "E"
        else material_sale_master.sale_text1_th,
        sale_text2=material_sale_master.sale_text2_en
        if language == "E"
        else material_sale_master.sale_text2_th,
        sale_text3=material_sale_master.sale_text3_en
        if language == "E"
        else material_sale_master.sale_text3_th,
        sale_text4=material_sale_master.sale_text4_en
        if language == "E"
        else material_sale_master.sale_text4_th,
    )
    if material_sale_master.item_category_group == BOM_ITEM_CATEGORY_GROUP:
        order_line.bom_flag = True
        order_line.weight = 0
        order_line.weight_unit = product_material.weight_unit
    if sold_to_channel_master:
        order_line.price_currency = sold_to_channel_master.currency
        order_line.delivery_tol_over = sold_to_channel_master.over_delivery_tol
        order_line.delivery_tol_under = sold_to_channel_master.under_delivery_tol
    if order.status_sap == ScgOrderStatusSAP.COMPLETE.value:
        order_line.draft = True
    return order_line


def get_bom_order_lines(order_line, order, sold_to_channel_master):
    bom_order_lines = []
    bom_materials = BomMaterialRepo.get_bom_mat_by_parent_material_code_and_date(
        order_line.material_code, timezone.now().date()
    )
    if not bom_materials:
        raise ValidationError("BOM child not found!")
    for bom_material in bom_materials:
        order_line_bom = construct_order_line_object(
            bom_material.material_code,
            order,
            sold_to_channel_master,
        )
        order_line_bom.bom_flag = True
        order_line_bom.parent = order_line
        bom_order_lines.append(order_line_bom)
    return bom_order_lines


def get_conversion_master(material_code):
    return Conversion2MasterRepo.get_conversion_by_material_code(material_code)


def update_otc_ship_to(info, line_id, data):
    order_line = OrderLineRepo.get_order_line(line_id)
    otc_ship_to = order_line.otc_ship_to
    return (
        update_otc_partner(data, info, otc_ship_to)
        if otc_ship_to
        else create_otc_partner(data, info, order_line)
    )


def update_otc_partner(data, info, otc_partner):
    address = prepare_otc_partner_address_update(data, otc_partner.address)
    otc_partner_count = OrderRepo.get_otc_partner_count(otc_partner.order)
    address.address_code = str(otc_partner_count + 1).zfill(5)
    OrderRepo.save_order_otc_partneraddress(address)
    otc_partner.sold_to_code = data.get("sold_to_code")
    return OrderRepo.save_order_otc_partner(otc_partner)


def create_otc_partner(data, info, order_line):
    address = prepare_otc_partner_address_update(data, OrderOtcPartnerAddress())
    otc_partner_count = OrderRepo.get_otc_partner_count(order_line.order)
    address.address_code = str(otc_partner_count + 1).zfill(5)
    OrderRepo.save_order_otc_partneraddress(address)
    otc_partner = sap_migration_models.OrderOtcPartner(
        sold_to_code=data.get("sold_to_code"),
        partner_role=RealtimePartnerType.SHIP_TO.value,
    )
    otc_partner.address = address
    otc_partner.order = order_line.order
    OrderRepo.save_order_otc_partner(otc_partner)
    order_line.otc_ship_to = otc_partner
    OrderLineRepo.save_order_line(order_line)
    return otc_partner


@transaction.atomic
def delete_otc_ship_to(line_id):
    order_line = OrderLineRepo.get_order_line(line_id)
    otc_ship_to = order_line.otc_ship_to
    if otc_ship_to:
        order_line.otc_ship_to = None
        OrderLineRepo.update_order_line(order_line, ["otc_ship_to"])
        OrderOtcPartnerAddressRepo.delete_otc_partner_address(otc_ship_to.address)


@transaction.atomic
def cancel_delete_cip_order_lines(so_no, order_lines_input, info):
    logging.info(
        f" [No Ref Contract -  Cancel/Delete] For the order {so_no} Order Lines : {order_lines_input} "
        f" by user: {info.context.user}"
    )
    success = True
    sap_order_messages_response = []
    sap_item_messages_response = []
    sap_order_message_being_process = []
    order = OrderRepo.get_order_by_so_no(so_no)
    item_nos = [order_line["item_no"] for order_line in order_lines_input]
    order_lines_db = OrderLineRepo.get_order_line_by_order_no_and_item_no(
        so_no, item_nos
    )

    if not order or not order_lines_db:
        raise ValidationError("Invalid Order details")

    order_lines = order_lines_db.in_bulk(field_name="item_no")

    if order_lines_input[0].get("status") == OrderLineStatus.DELETE.value:
        validate_order_for_delete(order)
        validate_parent_child_selected_bom_delete(order_lines)

    try:
        params_for_es18 = prepare_params_for_cancel_delete_es18(
            so_no, order_lines_input, order_lines
        )
        logging.info("[No Ref Contract -  Cancel/Delete] calling... ES18")
        sap_response = change_order_update(params_for_es18)
        logging.info("[No Ref Contract -  Cancel/Delete] called ES18")
    except Exception as e:
        logging.error(
            f"[No Ref Contract -  Cancel/Delete] An Exception occurred: {str(e)}"
        )
        if isinstance(e, ValidationError):
            raise e
        raise ImproperlyConfigured(e)

    sap_order_message_being_process, is_being_process = handle_case_being_process_sap(
        sap_response, so_no
    )
    logging.info(
        f"[No Ref Contract -  Cancel/Delete] sap_order_error_message: {sap_order_message_being_process},"
        f"is_order_being_processed by other user : {is_being_process}"
    )
    if sap_order_message_being_process and is_being_process:
        return success, sap_order_message_being_process, sap_item_messages_response

    (
        success,
        sap_order_message,
        sap_item_messages,
        *_,
    ) = get_error_messages_from_sap_response(sap_response)
    logging.info(
        f"[No Ref Contract -  Cancel/Delete] sap_order_error_message: {sap_order_message},"
        f"sap_item_error_messages : {sap_item_messages}"
    )
    if not success or sap_order_message or sap_item_messages:
        sap_order_messages_response = sap_order_message
        sap_item_messages_response = sap_item_messages
        success = False
        return (success, sap_order_messages_response, sap_item_messages_response)
    # SAP:ES18 response is success
    update_cancel_delete_order_lines(info, order_lines_input, order_lines, order)
    return (success, sap_order_messages_response, sap_item_messages_response)


def get_error_messages_from_sap_response(sap_response):
    return (
        sap_response.get("success"),
        sap_response.get("sap_order_messages"),
        sap_response.get("sap_item_messages"),
    )


def validate_order_for_delete(order):
    if order.order_type == CIPOrderPaymentType.CASH:
        raise ValidationError(f"Cannot delete Order Type {order.order_type}")


def validate_parent_child_selected_bom_delete(orderline_dic):
    parent_child_order_items_dict = {}
    get_bom_parent_child_item_no_dict(orderline_dic, parent_child_order_items_dict)
    if not parent_child_order_items_dict:
        return

    for parent in parent_child_order_items_dict:
        child_items = parent_child_order_items_dict[parent]
        is_all_child_deleted = True
        parent_id = orderline_dic.get(parent).id
        bom_db_lines = OrderLineRepo.get_bom_order_lines_by_parent_id(parent_id)
        for child in bom_db_lines:
            if is_valid_item_status_to_delete(child):
                if child.item_no not in child_items:
                    is_all_child_deleted = False
                    break
            else:
                if child.item_no in child_items:
                    raise ValidationError(
                        f"Cannot delete Item {child.item_no} with status {child.item_status_en}"
                    )
                else:
                    is_all_child_deleted = False
                    break

        """
        if all the child records deleted then check the respective parent is deleted
        """
        if is_all_child_deleted:
            if parent not in orderline_dic:
                raise ValidationError(
                    f"Cannot delete only child record for BOM Item {parent} "
                )
        else:
            raise ValidationError(
                f"Cannot delete BOM Item {parent} without selecting all Child items "
            )

    return False


def get_bom_parent_child_item_no_dict(order_lines, parent_child_order_items_dict):
    for order_line in order_lines.values():
        if order_line.bom_flag and order_line.parent:
            parent_item_no = order_line.parent.item_no
            if parent_child_order_items_dict.get(parent_item_no):
                parent_child_order_items_dict.get(parent_item_no).append(
                    order_line.item_no
                )
            else:
                parent_child_order_items_dict[parent_item_no] = [order_line.item_no]
        elif order_line.bom_flag:
            parent_item_no = order_line.item_no
            if not parent_child_order_items_dict.get(parent_item_no):
                parent_child_order_items_dict[parent_item_no] = None


def update_cancel_delete_order_lines(info, order_lines_input, order_lines, order):
    update_cancel_93_lines = []
    delete_lines = []
    for order_line in order_lines_input:
        line = order_lines.get(order_line.get("item_no"))
        if order_line["status"] == OrderLineStatus.CANCEL:
            update_cancel_93_lines.append(line)
        else:
            delete_lines.append(line)

    if update_cancel_93_lines:
        update_reject_reason_for_items(update_cancel_93_lines)
        status_en, status_thai = update_order_status(order.id)
        order.status = status_en
        order.status_thai = status_thai
        order.update_by = info.context.user
        logging.info(
            f"[No Ref Contract -  Cancel/Delete] Item {order_lines.keys()} Cancelled by  {info.context.user}"
        )
        OrderRepo.save_order(order)
    if delete_lines:
        order.update_by = info.context.user
        logging.info(
            f"[No Ref Contract -  Cancel/Delete] Item {order_lines.keys()} Deleted by  {info.context.user}"
        )
        OrderRepo.save_order(order)
        deleted_count = OrderLineRepo.delete_order_lines_by_ids(
            [item.id for item in delete_lines]
        )
        logging.info(
            f"[No Ref Contract -  Cancel/Delete] Item {order_lines.keys()} deleted_count   {deleted_count}"
        )


def update_reject_reason_for_items(order_lines):
    for line in order_lines:
        line.reject_reason = REASON_REJECT
        line.item_status_en = EorderingItemStatusEN.CANCEL.value
        line.item_status_th = EorderingItemStatusTH.CANCEL.value
        line.attention_type = None
        OrderLineRepo.update_order_line(
            line,
            ["reject_reason", "item_status_en", "item_status_th", "attention_type"],
        )


def cancel_cip_order(data, info):
    logging.info(
        f" [No Ref Contract -  Cancel/Delete] For the order {data.get('so_no', '')} FE request : {data} "
        f" by user: {info.context.user}"
    )
    so_no = data["so_no"]
    order = OrderRepo.get_order_by_so_no(so_no)
    if not order:
        raise ValidationError("Order Not Found")

    order_lines_input = []
    order_lines = OrderLineRepo.find_all_order_line_by_order(order)

    for order_line in order_lines:
        if not is_valid_item_status_to_cancel(order_line):
            continue
        order_lines_input.append({"item_no": order_line.item_no, "status": "Cancel"})

    if not order:
        raise ValidationError("No items Found")

    return cancel_delete_cip_order_lines(so_no, order_lines_input, info)


def is_valid_item_status_to_cancel(order_line):
    if order_line.item_status_en in [
        EorderingItemStatusEN.CANCEL.value,
        EorderingItemStatusEN.COMPLETE_DELIVERY.value,
    ]:
        return False
    return True


def is_valid_item_status_to_delete(order_line):
    if order_line.item_status_en in [
        EorderingItemStatusEN.ITEM_CREATED.value,
    ]:
        return True
    return False


def prepare_split_order_line_using_cp_response(
    dict_order_schedules_out,
    order_line_db,
    order_line,
    is_after_cp_confirm_pop_up=False,
):
    split_order_line = copy.deepcopy(order_line_db)
    split_order_line.pk = None
    split_order_line.parent = None
    split_order_line.origin_item = order_line_db
    split_order_line.quantity = order_line.quantity
    confirm_quantity = dict_order_schedules_out.get(str(order_line.item_no), 0)
    split_order_line.assigned_quantity = confirm_quantity
    split_order_line.confirm_quantity = confirm_quantity
    split_order_line.item_no = order_line.item_no
    split_order_line.request_date = order_line.request_date.strftime(YMD_FORMAT)
    if is_after_cp_confirm_pop_up:
        split_order_line.confirmed_date = order_line.confirm_date
        split_order_line.plant = order_line.plant
    else:
        split_order_line.confirmed_date = order_line.request_date.strftime(YMD_FORMAT)
    split_order_line.internal_comments_to_warehouse = (
        order_line.internal_comments_to_warehouse
    )
    split_order_line.external_comments_to_customer = (
        order_line.external_comments_to_customer
    )
    split_order_line.sale_text1 = order_line.sale_text_1
    split_order_line.sale_text2 = order_line.sale_text_2
    split_order_line.sale_text3 = order_line.sale_text_3
    split_order_line.sale_text4 = order_line.sale_text_4
    split_order_line.remark = order_line.remark
    split_order_line.item_note = order_line.item_note_cip
    split_order_line.pr_item_text = order_line.pr_item_text_cip
    split_order_line.lot_no = order_line.lot_no
    split_order_line.production_memo = order_line.production_memo_pp
    split_order_line.production_flag = order_line.production_flag
    return split_order_line


def update_order_line_after_split(
    dict_order_schedules_out,
    original_line_items,
    original_order_lines_obj_dict,
    cp_response_item_dict,
    is_after_cp_confirm_pop_up=False,
):
    for original_line in original_line_items:
        if original_order_lines_obj_dict and original_order_lines_obj_dict.get(
            original_line.id
        ):
            original_order_line_db = original_order_lines_obj_dict.get(original_line.id)
            original_order_line_db.quantity = original_line.quantity
            confirm_quantity = dict_order_schedules_out.get(
                str(original_order_line_db.item_no), 0
            )
            original_order_line_db.assigned_quantity = confirm_quantity
            original_order_line_db.confirm_quantity = confirm_quantity
            original_order_line_db.request_date = original_line.request_date
            if is_after_cp_confirm_pop_up:
                if original_line.plant:
                    original_order_line_db.plant = original_line.plant
                if original_line.confirm_date:
                    original_order_line_db.confirmed_date = original_line.confirm_date
            elif cp_response_item_dict and cp_response_item_dict.get(
                original_line.item_no
            ):
                cp_response_item = cp_response_item_dict.get(original_line.item_no)
                original_order_line_db.plant = cp_response_item.get("plant", "")
                confirm_date = datetime.strptime(
                    cp_response_item.get("confirm_date"), DMY_FORMAT
                ).strftime(YMD_FORMAT)
                original_order_line_db.confirmed_date = confirm_date


def update_line_additional_text_from_parent(line, parent):
    if not line.internal_comments_to_warehouse:
        line.internal_comments_to_warehouse = parent.internal_comments_to_warehouse
    if not line.external_comments_to_customer:
        line.external_comments_to_customer = parent.external_comments_to_customer
    if not line.sale_text1:
        line.sale_text1 = parent.sale_text1
    if not line.sale_text2:
        line.sale_text2 = parent.sale_text2
    if not line.sale_text3:
        line.sale_text3 = parent.sale_text3
    if not line.sale_text4:
        line.sale_text4 = parent.sale_text4
    if not line.remark:
        line.remark = parent.remark
    if not line.item_note:
        line.item_note = parent.item_note
    if not line.pr_item_text:
        line.pr_item_text = parent.pr_item_text
    if not line.lot_no:
        line.lot_no = parent.lot_no
    if not line.production_memo:
        line.production_memo = parent.production_memo
    if not line.production_flag:
        line.production_flag = parent.production_flag


@transaction.atomic
def save_order_lines_after_sap_split(
    so_no,
    cp_item_messages,
    original_line_items,
    original_lines_db,
    original_order_lines_obj_dict,
    sap_response,
    split_line_items,
    split_line_child_parent,
    is_after_cp_confirm_pop_up=False,
):
    try:
        if sap_response:
            order_schedules_outs = sap_response.get("orderSchedulesOut", [])
        dict_order_schedules_out = {
            str(order_schedule["itemNo"]).lstrip("0"): order_schedule["confirmQuantity"]
            for order_schedule in order_schedules_outs
        }
        cp_response_item_dict = {}
        if cp_item_messages:
            cp_response_item_dict = {
                cp_item_message.get("item_no"): cp_item_message
                for cp_item_message in cp_item_messages
            }
        update_order_line_after_split(
            dict_order_schedules_out,
            original_line_items,
            original_order_lines_obj_dict,
            cp_response_item_dict,
            is_after_cp_confirm_pop_up,
        )
        split_order_lines_to_save = []
        split_order_line_cps_to_save = []
        for split_line in split_line_items:
            if original_order_lines_obj_dict and original_order_lines_obj_dict.get(
                split_line.original_item_id
            ):
                order_line_db = original_order_lines_obj_dict.get(
                    split_line.original_item_id
                )
                split_order_line = prepare_split_order_line_using_cp_response(
                    dict_order_schedules_out,
                    order_line_db,
                    split_line,
                    is_after_cp_confirm_pop_up,
                )
                if split_line.is_parent:
                    split_order_lines_to_save.append(split_order_line)
                    continue
                (
                    cp_response_item,
                    split_order_line_cp,
                ) = prepare_cp_order_line_using_cp_item_messages(
                    cp_response_item_dict, order_line_db, split_order_line
                )
                if not is_after_cp_confirm_pop_up and cp_response_item:
                    split_order_line.confirmed_date = datetime.strptime(
                        cp_response_item.get("confirm_date"), DMY_FORMAT
                    ).strftime(YMD_FORMAT)
                    split_order_line.plant = cp_response_item.get("plant", "")
                split_order_lines_to_save.append(split_order_line)
                if split_order_line_cp:
                    split_order_line_cps_to_save.append(split_order_line_cp)
        OrderLineRepo.update_order_line_bulk(
            original_lines_db,
            [
                "quantity",
                "assigned_quantity",
                "confirm_quantity",
                "plant",
                "request_date",
                "confirmed_date",
            ],
        )
        if split_order_lines_to_save:
            created_split_order_lines = OrderLineRepo.save_order_line_bulk(
                split_order_lines_to_save
            )
            cp_lines_to_save_dict = None
            split_lines_to_save_dict = {
                line.item_no: line for line in split_order_lines_to_save
            }
            if split_order_line_cps_to_save:
                cp_lines_to_save_dict = {
                    line_cp.item_no: line_cp for line_cp in split_order_line_cps_to_save
                }
            for line in created_split_order_lines:
                if split_line_child_parent and split_line_child_parent.get(
                    line.item_no
                ):
                    split_parent_line_input = split_line_child_parent.get(line.item_no)
                    parent = split_lines_to_save_dict.get(
                        split_parent_line_input.item_no
                    )
                    line.parent = parent
                    update_line_additional_text_from_parent(line, parent)
                if cp_lines_to_save_dict and cp_lines_to_save_dict.get(line.item_no):
                    cp_line = cp_lines_to_save_dict.get(line.item_no)
                    cp_line.order_line = line
            OrderLineRepo.update_order_line_bulk(created_split_order_lines, ["parent"])
        if split_order_line_cps_to_save:
            OrderLineCpRepo.save_order_line_cp_bulk(split_order_line_cps_to_save)
    except Exception as e:
        logging.exception(
            f"[No Ref Contract -  Change Order:Split] "
            f"Exception while saving split updates on order: {so_no}"
        )
        transaction.set_rollback(True)
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)


def add_split_cip_order_lines(data):
    success = True
    cp_item_messages = []
    cp_error_messages = []
    sap_order_messages = []
    sap_item_messages = []
    so_no = data.get("so_no")
    original_line_items = data.get("origin_line_items")
    split_line_items = data.get("split_line_items")
    is_bom = data.get("is_bom")
    original_lines_db = OrderLineRepo.get_order_lines(
        [item.id for item in original_line_items]
    )
    original_line_items_dict = {}
    original_order_lines_obj_dict = {obj.id: obj for obj in original_lines_db}
    split_line_parent = None
    original_line_parent = None
    split_line_child_parent = {}
    # Filter Items which need Planning solution
    for original_line in original_line_items:
        if is_bom:
            if original_line.is_parent:
                original_line_parent = original_line
            else:
                split_line_child_parent[original_line.item_no] = original_line_parent
        original_line_items_dict[original_line.id] = original_line
    items_to_call_cp = filter_cp_order_line(original_lines_db, original_line_items_dict)
    for split_line in split_line_items:
        if is_bom:
            if split_line.is_parent:
                split_line_parent = split_line
            else:
                split_line_child_parent[split_line.item_no] = split_line_parent
        original_item = original_order_lines_obj_dict.get(split_line.original_item_id)
        if is_cp_planning_required(
            split_line.production_flag,
            is_bom,
            original_item.parent,
            original_item.material,
        ):
            items_to_call_cp.append(split_line)
    order = OrderRepo.get_order_by_so_no(so_no)
    order_extn = OrderRepo.get_order_extension_by_id(order.id)
    temp_order_no = order.so_no
    if order_extn:
        temp_order_no = order_extn.temp_order_no
    if items_to_call_cp:
        logging.info(
            f"[No Ref Contract -  Change Order:Split] Items which need Planning Solution are: "
            f" {[item.item_no for item in items_to_call_cp]} of order {so_no}"
        )
        try:
            from scgp_cip.service.create_order_service import call_cp

            cp_item_messages, cp_error_messages, cp_confirm_date_mismatch = call_cp(
                order,
                temp_order_no,
                items_to_call_cp,
                CPRequestType.CHANGED.value,
                original_order_lines_obj_dict,
                split_line_child_parent,
                False,
            )
            if (cp_confirm_date_mismatch and cp_item_messages) or cp_error_messages:
                success = False
                return {
                    "success": success,
                    "order": order,
                    "sap_order_messages": sap_order_messages,
                    "sap_item_messages": sap_item_messages,
                    "cp_item_messages": cp_item_messages,
                    "cp_error_messages": cp_error_messages,
                }

            (
                sap_order_messages,
                sap_item_messages,
                sap_response,
            ) = process_change_order_split_es_18(
                data,
                split_line_child_parent=split_line_child_parent,
                cp_item_messages=cp_item_messages,
            )
            if sap_order_messages or sap_item_messages:
                success = False
            else:
                # Save data into DB
                save_order_lines_after_sap_split(
                    so_no,
                    cp_item_messages,
                    original_line_items,
                    original_lines_db,
                    original_order_lines_obj_dict,
                    sap_response,
                    split_line_items,
                    split_line_child_parent,
                )
                if not cp_confirm_date_mismatch:
                    cp_item_messages = []
            return {
                "success": success,
                "order": order,
                "sap_order_messages": sap_order_messages,
                "sap_item_messages": sap_item_messages,
                "cp_item_messages": cp_item_messages,
                "cp_error_messages": cp_error_messages,
            }
        except Exception as e:
            logging.exception(
                f"[No Ref Contract -  Change Order:Split] With CP Planning order {order.so_no}"
                f" ran with exception {e}"
            )
            if isinstance(e, ConnectionError):
                raise ValueError("Error Code : 500 - Internal Server Error")
            raise ImproperlyConfigured(e)
    else:
        logging.info(
            f"[No Ref Contract -  Change Order:Split] Items which need CP Planning Solution are: NONE for Order {so_no}"
        )
        try:
            (
                sap_order_messages,
                sap_item_messages,
                sap_response,
            ) = process_change_order_split_es_18(
                data,
            )
            if sap_order_messages or sap_item_messages:
                success = False
            else:
                logging.info(
                    f"[No Ref Contract -  Change Order:Split] WITHOUT CP Planning order {order.so_no}"
                    f" - saving date after SAP request"
                )
                save_order_lines_after_sap_split(
                    so_no,
                    cp_item_messages,
                    original_line_items,
                    original_lines_db,
                    original_order_lines_obj_dict,
                    sap_response,
                    split_line_items,
                    split_line_child_parent,
                )
            return {
                "success": success,
                "order": order,
                "sap_order_messages": sap_order_messages,
                "sap_item_messages": sap_item_messages,
                "cp_item_messages": cp_item_messages,
                "cp_error_messages": cp_error_messages,
            }
        except Exception as e:
            logging.exception(
                f"[No Ref Contract -  Change Order:Split] WITHOUT CP Planning order {order.so_no}"
                f" ran with exception {e}"
            )
            if isinstance(e, ConnectionError):
                raise ValueError("Error Code : 500 - Internal Server Error")
            raise ImproperlyConfigured(e)


def cp_split_order_lines(data):
    success = True
    cp_item_messages = []
    cp_error_messages = []
    so_no = data.get("so_no")
    is_bom = data.get("is_bom")
    original_line_items = data.get("origin_line_items")
    split_line_items = data.get("split_line_items")
    original_lines_db = OrderLineRepo.get_order_lines(
        [item.id for item in original_line_items]
    )
    original_order_lines_obj_dict = {obj.id: obj for obj in original_lines_db}
    order = OrderRepo.get_order_by_so_no(so_no)
    split_line_child_parent = {}
    original_line_parent = None
    split_line_parent = None
    for original_line_input in original_line_items:
        if is_bom:
            if original_line_input.is_parent:
                original_line_parent = original_line_input
            else:
                split_line_child_parent[
                    original_line_input.item_no
                ] = original_line_parent
    for split_line_input in split_line_items:
        if is_bom:
            if split_line_input.is_parent:
                split_line_parent = split_line_input
            else:
                split_line_child_parent[split_line_input.item_no] = split_line_parent
    try:
        (
            sap_order_messages,
            sap_item_messages,
            sap_response,
        ) = process_change_order_split_es_18(
            data,
            is_after_cp_confirm_pop_up=True,
        )
        if sap_order_messages or sap_item_messages:
            success = False
        logging.info(
            f"[No Ref Contract -  Change Order:Split] After CP Planning"
            f" for order so_no: {so_no} saving date after SAP request"
        )
        save_order_lines_after_sap_split(
            so_no,
            cp_item_messages,
            original_line_items,
            original_lines_db,
            original_order_lines_obj_dict,
            sap_response,
            split_line_items,
            split_line_child_parent,
            is_after_cp_confirm_pop_up=True,
        )
        return {
            "success": success,
            "order": order,
            "cp_item_messages": cp_item_messages,
            "cp_error_messages": cp_error_messages,
            "sap_order_messages": sap_order_messages,
            "sap_item_messages": sap_item_messages,
        }

    except Exception as e:
        logging.exception(
            f"[No Ref Contract -  Change Order:Split] After CP Planning for order {order.so_no}"
            f" ran with exception {e}"
        )
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)


@transaction.atomic
def undo_cip_order_lines(data, info):
    success = False
    sap_order_messages_response = []
    sap_item_messages_response = []
    so_no = data["so_no"]
    item_no = data["item_no"]
    order = OrderRepo.get_order_by_so_no(so_no)
    order_line: OrderLines = OrderLineRepo.get_order_line_by_so_no_and_item_no(
        so_no, item_no
    )

    if order_line.item_status_en != CIPOrderItemStatus.CANCEL.value:
        logging.error(
            f"Invalid Item Status for Undo Cancel Action - So#: {so_no},"
            f" and Item #: {item_no}"
        )
        return (success, sap_order_messages_response, sap_item_messages_response)
    params_for_es18 = prepare_params_for_es18_undo(so_no, order_line, info)
    logging.info("[Domestic: Undo order lines] calling......ES18")
    sap_response = change_order_update(params_for_es18)

    sap_order_message_being_process, is_being_process = handle_case_being_process_sap(
        sap_response, so_no
    )
    logging.info(
        f"[No Ref Contract -  Cancel/Delete] sap_order_error_message: {sap_order_message_being_process},"
        f"is_order_being_processed by other user : {is_being_process}"
    )
    if sap_order_message_being_process and is_being_process:
        return success, sap_order_message_being_process, sap_item_messages_response

    (
        success,
        sap_order_message,
        sap_item_messages,
        *_,
    ) = get_error_messages_from_sap_response(sap_response)
    logging.info(
        f"[Domestic: Undo order lines] sap_order_error_message: {sap_order_messages_response},"
        f"sap_item_error_messages: {sap_item_messages_response}"
    )
    sap_order_messages_response = sap_order_message
    sap_item_messages_response = sap_item_messages

    if success:
        update_order_lines_for_undo(order_line, item_no)
        status_en, status_thai = update_order_status(order.id)
        logging.info(
            f"[Domestic: Undo order lines] DB order {order.so_no} status : {order.status} updated to {status_en}"
        )
        order.status = status_en
        order.status_thai = status_thai
        OrderRepo.save_order(order)
    logging.info(
        f"[Domestic: Undo order lines] Undo item {item_no} of order with SoNo : {order.so_no} is completed successfully"
    )
    return (success, sap_order_messages_response, sap_item_messages_response)


def update_order_lines_for_undo(order_line, item_no):
    order_line.item_status_en = EorderingItemStatusEN.ITEM_CREATED.value
    order_line.item_status_th = EorderingItemStatusTH.ITEM_CREATED.value
    OrderLineRepo.update_order_line(
        order_line,
        fields=[
            "item_status_en",
            "item_status_th",
        ],
    )
