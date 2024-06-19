# TODO: REVISIT NAME
import logging
from copy import deepcopy

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from common.cp.cp_helper import (
    filter_cp_order_line,
    prepare_cp_payload,
    prepare_order_line_update,
    process_cp_response,
)
from common.cp.cp_service import save_order_line_cp
from sap_migration.graphql.enums import CreatedFlow, OrderType
from scg_checkout.graphql.enums import (
    PaymentTerm,
    RealtimePartnerType,
    ScgOrderStatus,
    ScgOrderStatusSAP,
)
from scg_checkout.graphql.helper import add_sale_org_prefix
from scg_checkout.graphql.implementations.sap import (
    get_error_messages_from_sap_response_for_create_order,
)
from scg_checkout.graphql.validators import (
    validate_delivery_tol,
    validate_object,
    validate_objects,
)
from scgp_cip.common.constants import BOM_ITEM_CATEGORY_GROUP
from scgp_cip.common.enum import (
    CipOrderInput,
    CIPOrderItemStatus,
    CPRequestType,
    OrderInformationSubmit,
    OrderLines,
    OrderOrganizationDataSubmit,
    OrderSolutionThirdPartySystem,
)
from scgp_cip.dao.order.distribution_channel_master_repo import (
    DistributionChannelMasterRepo,
)
from scgp_cip.dao.order.division_master_repo import DivisionMasterRepo
from scgp_cip.dao.order.email_config_repo import (
    EmailConfigurationExternalRepo,
    EmailConfigurationInternalRepo,
)
from scgp_cip.dao.order.order_repo import OrderRepo
from scgp_cip.dao.order.sale_organization_master_repo import SalesOrganizationMasterRepo
from scgp_cip.dao.order.sales_group_master_repo import SalesGroupMasterRepo
from scgp_cip.dao.order.sold_to_master_repo import SoldToMasterRepo
from scgp_cip.dao.order_line.bom_material_repo import BomMaterialRepo
from scgp_cip.dao.order_line.material_master_repo import MaterialMasterRepo
from scgp_cip.dao.order_line.material_sale_master_repo import MaterialSaleMasterRepo
from scgp_cip.dao.order_line.order_line_repo import OrderLineRepo
from scgp_cip.dao.order_line.sold_to_material_master_repo import (
    SoldToMaterialMasterRepo,
)
from scgp_cip.dao.sold_to.sold_to_channel_master_repo import (
    SoldToChannelMasterRepository,
)
from scgp_cip.service.helper.create_order_helper import (
    derive_order_partners,
    es_16_params,
    es_16_params_for_excell_upload,
    generate_temp_so_no,
    get_partner_emails_from_es16_response,
    get_sap_warning_messages,
    prepare_excel_order_cip,
    prepare_excel_order_line_cip,
    prepare_order_for_cip_create,
    prepare_order_for_cip_update,
    prepare_orderline_for_cip_create,
    prepare_orderline_for_cip_update,
    prepare_otc_partner_create,
    prepare_otc_partneraddress_create,
    prepare_otc_partneraddress_update,
)
from scgp_cip.service.integration.integration_service import create_order, get_solution
from scgp_cip.service.orders_pdf_and_email_service import (
    send_mail_customer_create_order_cp,
)
from scgp_user_management.models import (
    EmailConfigurationFeatureChoices,
    EmailInternalMapping,
)


def create_or_update_cip_order(order_id, params, info):
    """This method creates/updates an order for CIP."""

    logging.info(
        f"[Create or Update CIP order] for Order id: {order_id}, FE request payload: {params}"
        f" by user: {info.context.user}"
    )

    if order_id:
        if params.get("status") and params.get("status") == ScgOrderStatus.CONFIRMED:
            try:
                params["status"] = ScgOrderStatus.DRAFT.value
                update_cip_order(order_id, params, info)

                # Second transaction for save_cip_order
                params["status"] = ScgOrderStatus.CONFIRMED.value
                submit_validate(params)
                return save_cip_order(order_id, params, info)
            except Exception as e:
                logging.exception(f"Error in create_or_update_cip_order {order_id}")
                raise e
        else:
            return update_cip_order(order_id, params, info)
    else:
        return create_cip_order(params, info)


def submit_validate(data):
    if data.get("status", None) != ScgOrderStatus.CONFIRMED.value:
        return
    validate_object(
        data.order_information,
        CipOrderInput.ORDER_INFORMATION.value,
        OrderInformationSubmit.REQUIRED_FIELDS.value,
    )
    validate_object(
        data.order_organization_data,
        CipOrderInput.ORDER_ORGANIZATION_DATA.value,
        OrderOrganizationDataSubmit.REQUIRED_FIELDS.value,
    )
    validate_objects(
        data.lines,
        CipOrderInput.LINES.value,
        OrderLines.REQUIRED_FIELDS.value,
    )

    validate_delivery_tol(data.lines)


def validate_update_order_status(status, order=None):
    if status:
        if not (status == ScgOrderStatus.PRE_DRAFT or status == ScgOrderStatus.DRAFT):
            raise ValueError(f"value of Status can't be {status} ")
    else:
        raise ValueError("value of Status can't be empty ")

    if order and not (
        order.status == ScgOrderStatus.PRE_DRAFT.value
        or order.status == ScgOrderStatus.DRAFT.value
    ):
        raise ValueError(f"Cannot update order with status {order.status} ")


def validate_and_prepare_organization_data(order_organization_data, channel_master):
    sales_organization_code = order_organization_data.get("sale_organization_code")
    sale_org = validate_sales_organization(sales_organization_code)
    order_organization_data["sale_organization_id"] = sale_org.id
    order_organization_data["bu"] = sale_org.business_unit.code

    distribution_channel_code = order_organization_data.get("distribution_channel_code")
    dist_channel = validate_distribution_channel(distribution_channel_code)
    order_organization_data["distribution_channel_id"] = dist_channel.id

    division_code = order_organization_data.get("division_code")
    division = validate_division(division_code)
    order_organization_data["division_id"] = division.id

    sale_group_code = order_organization_data.get("sale_group_code")
    if sale_group_code:
        sales_group = validate_sales_group(sale_group_code)
        order_organization_data["sale_group_id"] = sales_group.id


def validate_sales_group(sale_group_code):
    sales_group = SalesGroupMasterRepo.get_sales_group_by_code(sale_group_code)
    if not sales_group:
        raise ValueError(f"invalid sale_group_code {sale_group_code} ")
    return sales_group


def validate_division(division_code):
    division = DivisionMasterRepo.get_division_by_code(division_code)
    if not division:
        raise ValueError(f"invalid division_code {division_code} ")
    return division


def validate_distribution_channel(distribution_channel_code):
    dist_channel = DistributionChannelMasterRepo.get_distribution_channel_by_code(
        distribution_channel_code
    )
    if not dist_channel:
        raise ValueError(
            f"invalid distribution_channel_code {distribution_channel_code} "
        )
    return dist_channel


def validate_sales_organization(sales_organization_code):
    sale_org = SalesOrganizationMasterRepo.get_sale_organization_by_code(
        sales_organization_code
    )
    if not sale_org:
        raise ValueError(f"invalid sale_organization_code {sales_organization_code} ")
    return sale_org


def get_channel_master(order_information, order_organization_data):
    return SoldToChannelMasterRepository.get_by_sales_info(
        order_information.get("sold_to_code"),
        order_organization_data.get("sale_organization_code"),
        order_organization_data.get("distribution_channel_code"),
    )


def prepare_and_create_otc_partner(info, orderext, otc_info, partner_role):
    address = prepare_otc_partneraddress_create(otc_info)
    address.created_by = info.context.user
    OrderRepo.save_order_otc_partneraddress(address)
    partner = prepare_otc_partner_create(otc_info, partner_role)
    partner.address = address
    partner.order = orderext.order
    partner.created_by = info.context.user
    return OrderRepo.save_order_otc_partner(partner)


def prepare_and_update_otc_partner(info, orderext, otc_info, partner):
    address = prepare_otc_partneraddress_update(otc_info, partner.address)
    role_to_code = {
        RealtimePartnerType.SOLD_TO.value: "00001",
        RealtimePartnerType.SHIP_TO.value: "00002",
        RealtimePartnerType.BILL_TO.value: "00003",
    }
    address.address_code = role_to_code.get(partner.partner_role, "")
    address.last_updated_by = info.context.user
    OrderRepo.save_order_otc_partneraddress(address)

    partner.sold_to_code = otc_info.get("sold_to_code")
    partner.last_updated_by = info.context.user
    return OrderRepo.save_order_otc_partner(partner)


def check_and_create_otc_sold_to(info, otc_soldto, orderext):
    partner = prepare_and_create_otc_partner(
        info, orderext, otc_soldto, RealtimePartnerType.SOLD_TO.value
    )
    orderext.otc_sold_to = partner
    return orderext


def check_and_create_otc_bill_to(info, otc_billto, orderext):
    partner = prepare_and_create_otc_partner(
        info, orderext, otc_billto, RealtimePartnerType.BILL_TO.value
    )
    orderext.otc_bill_to = partner
    return orderext


def check_and_create_otc_ship_to(info, otc_shipto, orderext):
    partner = prepare_and_create_otc_partner(
        info, orderext, otc_shipto, RealtimePartnerType.SHIP_TO.value
    )
    orderext.otc_ship_to = partner
    return orderext


def check_and_update_otc_sold_to(info, otc_soldto, orderext):
    if orderext.otc_sold_to:
        prepare_and_update_otc_partner(info, orderext, otc_soldto, orderext.otc_sold_to)
    else:
        partner = prepare_and_create_otc_partner(
            info, orderext, otc_soldto, RealtimePartnerType.SOLD_TO.value
        )
        orderext.otc_sold_to = partner
    return orderext


def check_and_update_otc_bill_to(info, otc_billto, orderext):
    if orderext.otc_bill_to:
        prepare_and_update_otc_partner(info, orderext, otc_billto, orderext.otc_bill_to)
    else:
        partner = prepare_and_create_otc_partner(
            info, orderext, otc_billto, RealtimePartnerType.BILL_TO.value
        )
        orderext.otc_bill_to = partner
    return orderext


def check_and_update_otc_ship_to(info, otc_shipto, orderext):
    if orderext.otc_ship_to:
        prepare_and_update_otc_partner(info, orderext, otc_shipto, orderext.otc_ship_to)
    else:
        partner = prepare_and_create_otc_partner(
            info, orderext, otc_shipto, RealtimePartnerType.SHIP_TO.value
        )
        orderext.otc_ship_to = partner
    return orderext


@transaction.atomic
def create_cip_order(params, info):
    """This method creates a Draft/Pre-draft order with the parameters received"""
    # result = "success"  # TODO

    logging.info(
        f" [Create or Update CIP order] Create CIP order  , FE request payload: {params}"
        f" by user: {info.context.user} "
    )

    order_information = params.pop("order_information")
    order_organization_data = params.pop("order_organization_data")
    order_lines_info = params.get("lines")
    status = params.get("status")

    validate_update_order_status(status)

    channel_master = get_channel_master(order_information, order_organization_data)

    validate_and_prepare_organization_data(order_organization_data, channel_master)

    order, order_extn = prepare_order_for_cip_create(
        info, order_information, order_organization_data
    )
    # mock so_no
    order.so_no = generate_temp_so_no()
    order_extn.temp_order_no = order.so_no
    order.type = OrderType.DOMESTIC.value
    order.created_by_flow = CreatedFlow.DOMESTIC_EORDERING.value
    order.created_by = info.context.user
    order.status = status
    order = OrderRepo.save_order(order)

    order_extn.order = order
    order_extn.created_by = info.context.user
    otc_sold_to = order_information.get("otc_sold_to")
    if otc_sold_to:
        order_extn = check_and_create_otc_sold_to(info, otc_sold_to, order_extn)

    otc_bill_to = order_information.get("otc_bill_to")
    if otc_bill_to:
        order_extn = check_and_create_otc_bill_to(info, otc_bill_to, order_extn)

    otc_ship_to = order_information.get("otc_ship_to")
    if otc_ship_to:
        order_extn = check_and_create_otc_ship_to(info, otc_ship_to, order_extn)

    order_extn = OrderRepo.save_order_extension(order_extn)

    if order_lines_info:
        orderlines = []

        for order_line in order_lines_info:
            line = prepare_orderline_for_cip_create(order, order_line, channel_master)
            line.order = order
            orderlines.append(line)

        OrderLineRepo.save_order_line_bulk(orderlines)

    return order


@transaction.atomic
def update_cip_order(order_id, params, info):
    """This method update an existing order with Draft/Pre-draft status with the parameters received"""
    # result = "success"  # TODO

    logging.info(
        f" [Create or Update CIP order] for Order id: {order_id} , FE request payload: {params}"
        f" by user: {info.context.user} "
    )

    order_information = params.pop("order_information")
    order_organization_data = params.pop("order_organization_data")
    order_lines_info = params.get("lines")
    status = params.get("status")

    order = OrderRepo.get_order_by_id(order_id)
    if not order:
        logging.info(
            f"   [Create or Update CIP order] ValidationError while updating CIP order for Order id: {order_id} . Order Not found"
            f" by user: {info.context.user}"
        )
        raise ValueError(f"Invalid order Id {order_id} ")

    original_order = deepcopy(order)
    order_id = order.id

    logging.debug(
        f" [Create or Update CIP order] for Order id: {order_id} , original_order: {original_order}"
    )
    validate_update_order_status(status, order)
    order_extn = OrderRepo.get_order_extension_by_id(order_id)

    channel_master = get_channel_master(order_information, order_organization_data)
    validate_and_prepare_organization_data(order_organization_data, channel_master)

    order, order_extn = prepare_order_for_cip_update(
        info, order, order_extn, order_information, order_organization_data
    )
    order.status = status
    order.updated_by_id = info.context.user.pk
    order_extn.last_updated_by_id = info.context.user.pk
    otc_sold_to = order_information.get("otc_sold_to")
    if otc_sold_to:
        order_extn = check_and_update_otc_sold_to(info, otc_sold_to, order_extn)
    else:
        delete_otc_partner(order_extn.otc_sold_to)
        order_extn.otc_sold_to = None

    otc_bill_to = order_information.get("otc_bill_to")
    if otc_bill_to:
        order_extn = check_and_update_otc_bill_to(info, otc_bill_to, order_extn)
    else:
        delete_otc_partner(order_extn.otc_bill_to)
        order_extn.otc_bill_to = None

    otc_ship_to = order_information.get("otc_ship_to")
    if otc_ship_to:
        order_extn = check_and_update_otc_ship_to(info, otc_ship_to, order_extn)
    else:
        delete_otc_partner(order_extn.otc_ship_to)
        order_extn.otc_ship_to = None

    if order_lines_info:
        order_lines_db = OrderLineRepo.get_order_lines_by_order_id_without_split(
            order_id
        )
        if not order_lines_db:
            logging.info(
                f"  [Create or Update CIP order] ValidationError while updating CIP order for Order id: {order_id} . OrderLines Not found"
                f" by user: {info.context.user}"
            )
            raise ValueError(f"Error getting OrderLines for order Id {order_id} ")

        order_line_objects = {}
        orderlines = []
        for order_line in order_lines_db:
            order_line_objects[str(order_line.id)] = order_line
        order_item_map = {item["id"]: item for item in order_lines_info}
        for order_line in order_lines_info:

            order_line_db = order_line_objects.get(order_line.get("id"))
            if not order_line_db:
                line_id = order_line.get("id")
                logging.info(
                    f"   [Create or Update CIP order] ValidationError while updating CIP order for Order id: {order_id} . OrderLines Not found {line_id} "
                    f" by user: {info.context.user}"
                )
                raise ValueError(
                    f"Error getting OrderLines for order Line Id {line_id} "
                )
            material = MaterialMasterRepo.get_material_by_material_code(
                order_line.get("material_no")
            )
            if not material or material.id != order_line_db.material_id:
                raise ValueError(
                    f"Error updating OrderLines for order Line Id {order_line_db.id}. Request material {material.material_code if material else None} is different from DB {order_line_db.material_code} "
                )
            line = prepare_orderline_for_cip_update(
                order, order_line_db, order_line, order_item_map
            )
            orderlines.append(line)

        for order_line in orderlines:
            OrderLineRepo.save_order_line(order_line)

    """save the objects to DB """
    order_extn = OrderRepo.save_order_extension(order_extn)

    order = OrderRepo.save_order(order)

    return order


def delete_otc_partner(otc_partner):
    if otc_partner:
        if otc_partner.address:
            OrderRepo.delete_order_otc_partner_address(otc_partner.address)

        OrderRepo.delete_order_otc_partner(otc_partner)


@transaction.atomic
def create_or_update_cp_order(data, info):
    order_line_updates = []
    order_id = ""
    try:
        input_params = data.get("input", {})
        order_lines = input_params.get("lines", [])
        order_id = input_params.get("order_id", "")
        order = OrderRepo.get_order_by_id(order_id)
        order_lines_db = OrderLineRepo.find_all_order_line_by_order(order)
        for line in order_lines_db:
            for order_line in order_lines:
                if line.item_no == order_line["item_no"]:
                    line.request_date = order_line["request_date"]
                    order_line_updates.append(line)
        OrderLineRepo.bulk_update(order_line_updates, ["request_date"])
        user = info.context.user
        es16_response = call_es16(
            order_id, user, order, order_lines_db, info, input_params
        )
        return es16_response
    except Exception as e:
        logging.exception(f"Call ES-16 Exception: for order  {order.so_no}")
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)


def delete_order_in_db_to_avoid_duplication(sap_order_number):
    # Fetch orders with the given SAP order number
    orders = OrderRepo.get_order_so_no(sap_order_number)
    if not orders:
        return
    # Collect IDs of orders to avoid multiple queries
    order_ids = [order.id for order in orders]
    # Fetch order lines related to the orders
    order_lines_in_db = OrderLineRepo.get_order_line_by_orders(order_ids)
    # Delete order lines and iPlan entries
    order_lines_in_db.delete()
    # Delete the orders
    orders.delete()


def update_order(order, response, order_lines):
    order_status = ScgOrderStatus.RECEIVED_ORDER.value
    sap_order_status = ScgOrderStatusSAP.COMPLETE.value
    sap_order_number = response.get("salesdocument")
    order_header_out = response.get("orderHeaderOut")
    payer_code, payer_name = get_sales_employee(response.get("orderPartners", []))
    sales_employee = f"{payer_code} - {payer_name}"
    item_no_latest = 0
    if order_lines:
        item_no_latest = max(int(order_line.item_no) for order_line in order_lines)
    order.status = order_status
    order.status_sap = sap_order_status
    order.status_thai = CIPOrderItemStatus.CIP_ORDER_LINES_STATUS_TH.value.get(
        CIPOrderItemStatus.RECEIVED_ORDER.value
    )
    order.so_no = sap_order_number
    order.eo_no = sap_order_number
    order.item_no_latest = item_no_latest
    order.sales_employee = sales_employee
    order.saved_sap_at = timezone.now()
    delete_order_in_db_to_avoid_duplication(sap_order_number)
    if order_header_out:
        order.total_price = order_header_out.get("orderAmtBeforeVat", order.total_price)
        order.total_price_inc_tax = order_header_out.get(
            "orderAmtAfterVat", order.total_price_inc_tax
        )
        order.tax_amount = order_header_out.get("orderAmtVat", order.tax_amount)
    order.save()


def get_sales_employee(order_partners):
    partner_code = None
    sold_to_code = None
    for order_partner in order_partners:
        if RealtimePartnerType.SALE_EMPLOYEE.value == order_partner.get(
            "partnerRole", ""
        ):
            partner_code = order_partner.get("partnerNo", "")
        if RealtimePartnerType.SOLD_TO.value == order_partner.get("partnerRole", ""):
            sold_to_code = order_partner.get("partnerNo", "")
    sales_employee = resolve_display_text(partner_code, sold_to_code)
    return partner_code, sales_employee


def resolve_display_text(partner_code, sold_to_code):
    sold_to_name = SoldToMasterRepo.get_sold_to_partner_data(sold_to_code, partner_code)
    list_name = ["name1", "name2", "name3", "name4"]
    final_name = []
    for name in list_name:
        name_attr = getattr(sold_to_name, name, "")
        if name_attr:
            final_name.append(name_attr)
    return " ".join(final_name)


def update_order_line(order, response):
    order_line_updates = []
    order_schedule_out = response.get("orderSchedulesOut")
    order_header_out = response.get("orderHeaderOut")
    order_lines = OrderLineRepo.get_order_line_by_order_distinct_item_no(order)
    order_items_out = response.get("orderItemsOut")
    # Create a dictionary to store the fields to update for each item_no
    fields_to_update_dict = {}
    if order_items_out:
        for item in order_items_out:
            order_line = order_lines.get(item["itemNo"].lstrip("0"))
            if order_line:
                fields_to_update = {
                    "weight_unit_ton": item.get("weightUnitTon"),
                    "weight_unit": item.get("weightUnit"),
                    "net_weight_ton": item.get("netWeightTon"),
                    "gross_weight_ton": item.get("grossWeightTon"),
                }

                fields_to_update_dict[order_line.item_no] = fields_to_update

    if order_schedule_out:
        for item in order_schedule_out:
            order_line = order_lines.get(item["itemNo"].lstrip("0"))
            if order_line:
                confirm_quantity = item.get("comfirmQuantity", None)
                order_line.assigned_quantity = confirm_quantity
                order_line.sap_confirm_qty = confirm_quantity
                order_line.confirm_quantity = confirm_quantity
                fields_to_update = fields_to_update_dict.get(order_line.item_no, {})
                order_line.weight_unit_ton = fields_to_update.get("weight_unit_ton")
                order_line.weight_unit = fields_to_update.get("weight_unit")
                order_line.net_weight_ton = fields_to_update.get("net_weight_ton")
                order_line.gross_weight_ton = fields_to_update.get("gross_weight_ton")
                order_line.item_status_en = CIPOrderItemStatus.ITEM_CREATED.value
                order_line.item_status_th = (
                    CIPOrderItemStatus.CIP_ORDER_LINES_STATUS_TH.value.get(
                        CIPOrderItemStatus.ITEM_CREATED.value
                    )
                )
                order_line_updates.append(order_line)
            update_list = [
                "sap_confirm_qty",
                "assigned_quantity",
                "confirm_quantity",
                "request_date",
                "confirmed_date",
                "weight_unit_ton",
                "weight_unit",
                "net_weight_ton",
                "gross_weight_ton",
                "item_status_en",
                "item_status_th",
            ]
            OrderLineRepo.bulk_update(order_line_updates, update_list)

    if order_header_out:
        order.total_price = order_header_out.get("orderAmtBeforeVat", order.total_price)
        order.total_price_inc_tax = order_header_out.get(
            "orderAmtAfterVat", order.total_price_inc_tax
        )
        order.tax_amount = order_header_out.get("orderAmtVat", order.tax_amount)
        order.save()


@transaction.atomic
def save_cip_order(order_id, params, info):
    """This method saves an existing order with Draft/Pre-draft status to SAP."""
    success = False
    logging.info(
        f" Save CIP order for Order id: {order_id}, FE request payload: {params}"
        f" by user: {info.context.user}"
    )
    order = OrderRepo.get_order_by_id(order_id)
    order_lines = OrderLineRepo.find_all_order_line_by_order(order)
    cp_order_lines = filter_cp_order_line(order_lines)
    if cp_order_lines:
        cp_item_messages, cp_error_messages, cp_confirm_date_mismatch = call_cp(
            order, order.so_no, cp_order_lines, CPRequestType.NEW.value
        )
        if cp_confirm_date_mismatch or cp_error_messages:
            return {
                "success": success,
                "order": order,
                "cp_item_messages": cp_item_messages,
                "cp_error_messages": cp_error_messages,
            }
    try:
        user = info.context.user
        response = call_es16(order_id, user, order, order_lines, info, params)
        return response

    except Exception as e:
        logging.exception(f"Call ES-16 Exception: for order  {order.so_no}")
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)


def call_cp(
    order,
    temp_order_no,
    cp_order_lines,
    request_type,
    original_order_lines_obj_dict=None,
    split_line_child_parent=None,
    save_cp_response=True,
    **kwargs,
):
    try:
        cp_response = get_solution(
            OrderSolutionThirdPartySystem.CP.value,
            prepare_cp_payload(
                order,
                temp_order_no,
                cp_order_lines,
                request_type,
                original_order_lines_obj_dict,
                split_line_child_parent,
                **kwargs,
            ),
        )
        if cp_response:
            (
                cp_item_messages,
                cp_error_messages,
                cp_confirm_date_mismatch,
            ) = process_cp_response(
                cp_response,
                cp_order_lines,
                request_type,
                original_order_lines_obj_dict,
                split_line_child_parent,
            )
            if save_cp_response:
                save_order_line_cp(order, cp_order_lines, cp_response)
                prepare_order_line_update(cp_order_lines, cp_response)
                OrderLineRepo.update_order_line_bulk(cp_order_lines, ["confirmed_date"])
            return cp_item_messages, cp_error_messages, cp_confirm_date_mismatch
    except Exception as e:
        logging.exception(f"Call CP Exception: for order  {order.so_no}")
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)


def process_es16_response(es16_response, info, order, order_lines):
    (
        sap_success,
        sap_order_messages,
        sap_item_messages,
        sap_errors_code,
        order_header_msg,
        is_being_process,
        is_items_error,
        order_item_message,
    ) = get_error_messages_from_sap_response_for_create_order(es16_response)
    warning_messages = get_sap_warning_messages(es16_response)
    if sap_success:
        update_order(order, es16_response, order_lines)
        update_order_line(order, es16_response)
        partner_emails = get_partner_emails_from_es16_response(es16_response)
        user = info.context.user
        send_mail_customer_create_order_cp(
            info, order, user, partner_emails=partner_emails
        )
    response = {
        "success": sap_success,
        "order": order,
        "sap_order_messages": sap_order_messages,
        "sap_item_messages": sap_item_messages,
        "warning_messages": warning_messages,
    }
    return response


def process_es16_response_excel_upload(es16_response, order, order_lines):
    (
        sap_success,
        sap_order_messages,
        sap_item_messages,
        sap_errors_code,
        order_header_msg,
        is_being_process,
        is_items_error,
        order_item_message,
    ) = get_error_messages_from_sap_response_for_create_order(
        es16_response, file_upload=True, is_excel_upload=True
    )

    is_order_created = not (
        len(order_item_message) == len(order_lines) or len(sap_order_messages) > 0
    )
    if is_order_created:
        update_order(order, es16_response, order_lines)
        update_order_line(order, es16_response)
    return (
        es16_response,
        sap_success,
        order_item_message,
        sap_order_messages,
        is_order_created,
    )


def call_es16_for_excel_upload(order, order_lines):
    parent_child_item_no_dict = {}

    item_ship_to_dict = {}
    for line in order_lines:
        item_ship_to_dict[line.item_no] = line.ship_to
        if line.parent:
            parent_child_item_no_dict.setdefault(line.parent.item_no, []).append(
                line.item_no
            )

    order_partners = derive_order_partners(
        order.sold_to.sold_to_code,
        order.sales_employee,
        order.bill_to,
        order.ship_to,
        item_ship_to_dict,
        None,
        payer=order.payer,
    )
    request_payload_es_16 = es_16_params_for_excell_upload(
        order,
        order_lines,
        order_partners,
        parent_child_item_no_dict,
    )
    import time

    start_time = time.time()
    logging.info(f" request_payload_es_16_excel: {request_payload_es_16}")
    es_16_response = create_order(request_payload_es_16)
    end_time = time.time()
    processing_time = end_time - start_time
    logging.info(
        f" response es_16_excel: {es_16_response}, Processing Time: {processing_time} seconds"
    )
    return process_es16_response_excel_upload(es_16_response, order, order_lines)


def call_es16(order_id, user, order, order_lines, info, params_in):
    order_ext = OrderRepo.get_order_extension_by_id(order_id)
    order_otc_partners = OrderRepo.get_order_otc_partner(order)
    order_otc_partner_addresses = [
        otc_partner.address for otc_partner in order_otc_partners
    ]
    payment_term = order.payment_term or PaymentTerm.DEFAULT.value
    parent_child_item_no_dict = {}
    item_ship_to_dict = {}
    item_otc_dict = {}
    for line in order_lines:
        if line.otc_ship_to:
            item_otc_dict[line.item_no] = line.otc_ship_to.address.address_code
        item_ship_to_dict[line.item_no] = line.ship_to
        if line.parent:
            parent_child_item_no_dict.setdefault(line.parent.item_no, []).append(
                line.item_no
            )
    order_lines_info = params_in.get("lines")
    order_item_map = {item["item_no"]: item for item in order_lines_info}

    order_partners = derive_order_partners(
        order.sold_to.sold_to_code,
        order.sales_employee,
        order.bill_to,
        order.ship_to,
        item_ship_to_dict,
        item_otc_dict=item_otc_dict,
        order_otc_partners=order_otc_partners,
    )

    request_payload_es_16 = es_16_params(
        order,
        order_ext,
        order_lines,
        order_partners,
        payment_term,
        order_otc_partner_addresses,
        user,
        order_item_map,
        parent_child_item_no_dict,
    )
    import time

    start_time = time.time()
    logging.info(f" request_payload_es_16: {request_payload_es_16}")
    es_16_response = create_order(request_payload_es_16)
    end_time = time.time()
    processing_time = end_time - start_time
    logging.info(
        f" response es_16: {es_16_response}, Processing Time: {processing_time} seconds"
    )
    # from scgp_cip.api_examples.es_16_response import ES_16_API_SUCCESS_RESPONSE_BOM
    # es_16_response = ES_16_API_SUCCESS_RESPONSE_BOM
    return process_es16_response(es_16_response, info, order, order_lines)


def resolve_email_to_and_cc_by_bu_and_sold_to(kwargs):
    sold_to_code = kwargs.get("sold_to_code", "")
    sale_org_code = kwargs.get("sale_org_list", [])
    bu = kwargs.get("bu", "")
    to, cc = get_list_email_by_bu(
        [sold_to_code],
        sale_org_code,
        EmailConfigurationFeatureChoices.PENDING_ORDER,
        bu,
    )
    sold_to_master = SoldToMasterRepo.get_sold_to_data(sold_to_code)
    return cc, sold_to_master, to


def get_list_email_by_bu(sold_to_codes, sale_orgs, feature, bu):
    list_to, list_cc = get_list_email_by_mapping(
        sold_to_codes, sale_orgs, feature, bu, pending_order=True
    )
    return list_to, list_cc


def get_list_email_by_mapping(
    sold_to_codes,
    sale_orgs,
    feature,
    bu,
    order_confirmation=False,
    pending_order=False,
):
    list_cc, list_to = compute_to_and_cc_list(
        feature, order_confirmation, pending_order, bu, sale_orgs, sold_to_codes
    )
    return " , ".join(set(list_to)), " , ".join(set(list_cc))


def compute_to_and_cc_list(
    feature, order_confirmation, pending_order, bu, sale_orgs, sold_to_codes
):
    email_mapping_config = []
    if order_confirmation:
        email_mapping_config = (
            EmailConfigurationInternalRepo.get_by_order_confirmation_and_bu(
                bu, order_confirmation
            )
        )
    if pending_order:
        email_mapping_config = (
            EmailConfigurationInternalRepo.get_by_pending_order_and_bu(
                bu, pending_order
            )
        )
    list_to = []
    list_cc = []
    for config in email_mapping_config:
        list_email_internal_mapping = EmailInternalMapping.objects.filter(
            team=config.team,
            bu=bu,
            sale_org__in=add_sale_org_prefix(sale_orgs),
        )
        for email_internal_mapping in list_email_internal_mapping:
            list_cc = list_cc + email_internal_mapping.email.split(",")
    list_to, list_cc = get_email_to_and_cc(sold_to_codes, feature, list_to, list_cc)
    return list_cc, list_to


def get_email_to_and_cc(sold_to_codes, feature, list_to, list_cc):
    email_settings = EmailConfigurationExternalRepo.get_by_sold_to_and_feature(
        feature, sold_to_codes
    )
    if not email_settings and list_to and list_cc:
        return "", ""

    for setting in email_settings:
        if setting.mail_to:
            list_to.append(setting.mail_to)
        if setting.cc_to:
            list_cc.append(setting.cc_to)
    return list_to, list_cc


def create_cip_order_excel(header_data, items, user):
    order, order_extension = prepare_excel_order_cip(header_data, items[0], user)
    OrderRepo.save_order(order)
    OrderRepo.save_order_extension(order_extension)
    order_lines = []
    bom_order_lines = []
    item_no_excel_line_dic = {}
    for line in items:
        order_line, bom_order_line_set = prepare_order_lines_excel(order, line)
        item_no_excel_line_dic[order_line.item_no] = line
        order_lines.append(order_line)
        bom_order_lines.extend(bom_order_line_set)
    OrderLineRepo.save_order_line_bulk(order_lines)
    OrderLineRepo.save_order_line_bulk(bom_order_lines)
    return order, order_lines + bom_order_lines, item_no_excel_line_dic


def prepare_order_lines_excel(order, line):
    material, sold_to_material_code = get_material_for_excel_order(line)
    sales = MaterialSaleMasterRepo.get_material_sale_master_by_material_code(
        material.material_code,
        order.sales_organization.code,
        order.distribution_channel.code,
    )
    order_line = prepare_excel_order_line_cip(line, material, sales, order)
    order_line.customer_mat_35 = sold_to_material_code
    order.item_no_latest += 10
    order_line.item_no = str(order.item_no_latest)
    bom_order_lines = []
    if sales.item_category_group == BOM_ITEM_CATEGORY_GROUP:
        order_line.bom_flag = True
        bom_order_lines = prepare_bom_order_lines_excel(line, order, order_line)
    return order_line, bom_order_lines


def get_material_for_excel_order(line):
    material_code = line.get("material_code")
    sold_to_material_code = None
    if material_code:
        material = MaterialMasterRepo.get_material_by_material_code(material_code)
        if not material:
            sold_to_material = (
                SoldToMaterialMasterRepo.get_sold_to_material_by_sold_to_material_code(
                    material_code
                )
            )
            if sold_to_material:
                material = MaterialMasterRepo.get_material_by_material_code(
                    sold_to_material.material_code
                )
                sold_to_material_code = sold_to_material.sold_to_material_code
            else:
                raise ValueError(
                    f"invalid material_code/customer_material: {material_code}"
                )
    else:
        description = line.get("material_description")
        materials = MaterialMasterRepo.get_material_by_description_en(description)
        if materials.count() > 1:
            raise ValueError(
                f"multiple materials found with description: {description}"
            )
        elif materials.count() == 0:
            raise ValueError(f"material not found with description: {description}")
        material = materials.first()
    return material, sold_to_material_code


def prepare_bom_order_lines_excel(line, order, order_line):
    bom_order_lines = []
    bom_materials = BomMaterialRepo.get_bom_mat_by_parent_material_code_and_date(
        order_line.material_code, timezone.now().date()
    )
    if not bom_materials:
        raise ValueError(
            f"bom child not found for material: {order_line.material_code}"
        )
    for bom_material in bom_materials:
        material = MaterialMasterRepo.get_material_by_material_code(
            bom_material.material_code
        )
        sales = MaterialSaleMasterRepo.get_material_sale_master_by_material_code(
            bom_material.material_code,
            order.sales_organization.code,
            order.distribution_channel.code,
        )
        bom_order_line = prepare_excel_order_line_cip(line, material, sales, order)
        bom_order_line.bom_flag = True
        bom_order_line.parent = order_line
        bom_order_line.quantity = bom_material.quantity
        bom_order_line.original_quantity = bom_material.quantity
        order.item_no_latest += 10
        bom_order_line.item_no = str(order.item_no_latest)
        bom_order_lines.append(bom_order_line)
    return bom_order_lines
