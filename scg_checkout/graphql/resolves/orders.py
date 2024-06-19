import logging
import uuid

from django.db.models import Subquery, Q, IntegerField
import time
import json

from django.db.models.functions import Cast
from scg_checkout.graphql.helper import get_sold_to_partner

from common.helpers import get_item_scenario, is_allow_to_change_inquiry_method, format_sap_decimal_values_for_report, \
    add_is_not_ref_to_es_25_res
from common.enum import ChangeItemScenario, MulesoftServiceType, MulesoftFeatureType
from common.mulesoft_api import MulesoftApiRequest
from common.product_group import SalesUnitEnum
from sap_migration.graphql.enums import OrderType
from sap_migration.models import (
    OrderLines,
    ContractMaterial,
    Contract
)
from scg_checkout import models
from sap_migration import models as migration_models
from sap_master_data import models as master_models
from scg_checkout.graphql.enums import (
    OrderLineStatus,
    SapOrderConfirmationStatus,
    IPlanOrderItemStatus,
    SapOrderConfirmationStatusParam, AtpCtpStatus,
)
from scg_checkout.graphql.helper import (
    from_api_response_es25_to_change_order,
    PAYMENT_TERM_MAPPING,
    remove_padding_zero_from_ship_to,
    sort_order_confirmation_data_item_by_status,
    get_list_status_from_es25_data_item,
    prepare_param_for_api_get_lms_report, prepare_param_for_api_get_gps_report
)
from scg_checkout.graphql.helper import prepare_param_for_es25_order_confirmation
from scgp_export.graphql.enums import SapEnpoint
from scgp_export.graphql.helper import sync_export_order_from_es26
from scgp_require_attention_items.graphql.helper import prepare_param_for_es25
from scgp_require_attention_items.graphql.resolvers.require_attention_items import call_es25_and_get_response

logger = logging.getLogger(__name__)


# info.variable_values.update({"sap_order_response": response})
def resolve_contract_order(info, id):
    order = migration_models.Order.objects.filter(id=id).first()
    return order


def resolve_contract_order_by_so_no(info, so_no):
    order = migration_models.Order.objects.filter(so_no=so_no).first()
    _so_no = order and order.so_no or so_no
    response = call_sap_es26(so_no=_so_no, sap_fn=info.context.plugins.call_api_sap_client)
    info.variable_values.update({"sap_order_response": response})
    return order


def resolve_contract_order_by_so_no_change(info, so_no):
    response = call_sap_es26(so_no=so_no, sap_fn=info.context.plugins.call_api_sap_client)
    sync_export_order_from_es26(response)
    info.variable_values.update({"sap_order_response": response})
    return response


def resolve_contract_orders():
    orders = models.TempOrder.objects.all()
    return orders


def resolve_contract_order_lines(id):
    return OrderLines.objects.filter(order_id=id).order_by("item_no")


def resolve_contract_order_lines_without_split(id):
    return OrderLines.objects.filter(order_id=id, original_order_line_id=None).annotate(
        fkn_int_cast=Cast('item_no', output_field=IntegerField()),
    ).order_by('fkn_int_cast', 'pk')


def resolve_contract_order_no(id):
    return OrderLines.objects.filter(order_id=id).first().order.contract.code


def resolve_contract_product(id):
    return models.ContractProduct.objects.get(id=id)


def resolve_contract_by_contract_product_id(contract_product_id):
    contract_id = ContractMaterial.objects.get(id=contract_product_id).contract_id
    return Contract.objects.get(id=contract_id)


def resolve_order_drafts(user):
    return migration_models.Order.objects.filter(status="draft", created_by=user)


def resolve_domestic_sold_tos():
    return master_models.SoldToMaster.objects.all()


def resolve_domestic_material_code_name_domestic_order(qs):
    return migration_models.MaterialVariantMaster.objects.filter(code__in=qs).exclude(material__delete_flag="X")


def resolve_sale_employee_domestic_order():
    return migration_models.SalesEmployee.objects.all()


def resolve_filter_domestic_business_unit():
    return migration_models.BusinessUnits.objects.all().order_by("name", "id")


def resolve_filter_domestic_company():
    return master_models.CompanyMaster.objects.all()


def resolve_filter_domestic_sales_group():
    return migration_models.SalesGroupMaster.objects.all()


def resolve_domestic_orders():
    return migration_models.Order.objects.filter(distribution_channel__code__in=['10', '20']).all()


def resolve_domestic_enum(enum):
    status = [(key, val.value) for key, val in vars(enum).items() if not key.startswith("_")]
    return status


def resolve_domestic_order_type():
    return migration_models.Order.objects.filter(pk__in=Subquery(
        migration_models.Order.objects.distinct("order_type").values("pk")
    )).exclude(Q(order_type__isnull=True) | Q(order_type=""))


def resolve_order_lines_iplan(order_id):
    iplan_ids = migration_models.OrderLines.objects.filter(order_id=order_id).values_list("iplan_id", flat=True)
    return migration_models.OrderLineIPlan.objects.filter(pk__in=iplan_ids).all()


def resolve_customer_1_group():
    return master_models.CustomerGroup1Master.objects.all()


def resolve_customer_2_group():
    return master_models.CustomerGroup2Master.objects.all()


def resolve_customer_3_group():
    return master_models.CustomerGroup3Master.objects.all()


def resolve_customer_4_group():
    return master_models.CustomerGroup4Master.objects.all()


def resolve_incoterms_1():
    return master_models.Incoterms1Master.objects.all()


def resolve_order_quantity_ton(root, info):
    try:
        quantity = root.quantity
        conversion = master_models.Conversion2Master.objects.filter(
            material_code__in=[root.material_variant.code, root.material.material_code], to_unit="ROL").last()

        if conversion:
            calculation = conversion.calculation
            order_quantity_ton = float(quantity) * float(calculation) / 1000
            return order_quantity_ton

        return root.quantity

    except Exception:
        return root.quantity


def resolve_currency(currency_id):
    try:
        return migration_models.CurrencyMaster.objects.filter(id=currency_id).first().code
    except Exception:
        return None


def resolve_preview_contract_order(info, id):
    order = migration_models.Order.objects.filter(id=id, status=OrderLineStatus.ENABLE.value).first()
    return order


def resolve_split_items(order_line_id):
    return migration_models.OrderLines.objects.filter(original_order_line_id=order_line_id).all()


def resolve_sales_unit_order(root, info):
    try:
        material_code = root.material_variant.code
        material_sale_master = master_models.MaterialSaleMaster.objects.filter(material_code=material_code).first()
        sales_unit = material_sale_master.sales_unit
        return sales_unit

    except Exception:
        return None


def resolve_weight(root, info):
    try:
        conversion = master_models.Conversion2Master.objects.filter(
            material_code__in=[root.material_variant.code], to_unit="ROL").last()

        if conversion:
            calculation = conversion.calculation
            order_quantity_ton = float(calculation) / 1000
            return order_quantity_ton

        return root.quantity

    except Exception:
        return root.quantity


def get_atp_ctp_popup_response(lines):
    item_status_rank = IPlanOrderItemStatus.IPLAN_ORDER_LINE_RANK.value
    lines_has_actual_gi_date = []
    lines_has_invalid_status = []

    for line in lines:
        if line.actual_gi_date:
            lines_has_actual_gi_date.append(line)
        if (item_status := line.item_status_en) and (line.iplan.order_type == "CTP"):
            item_status_index = item_status_rank.index(item_status)
            '''
            SEO-5332: 
                a) Order items with IPlan: ATP and Item Status Rank < Partial Delivery then allow user to edit
                b) Order items with IPlan: ATP and Item Status Rank >= Partial Delivery then UI disables ATP/CTP. 
                   Just in case if UI doesn't handle we are handling with below code
            '''
            if AtpCtpStatus.ATP.value == line.iplan.atp_ctp and item_status_index >= item_status_rank.index(
                    IPlanOrderItemStatus.PARTIAL_DELIVERY.value):
                lines_has_invalid_status.append(line)
            if AtpCtpStatus.CTP.value == line.iplan.atp_ctp and item_status_rank.index(
                    IPlanOrderItemStatus.PLANNING_CONFIRM.value) < item_status_index < item_status_rank.index(
                    IPlanOrderItemStatus.PARTIAL_DELIVERY.value) and item_status_index != item_status_rank.index(
                    IPlanOrderItemStatus.PLANNING_OUTSOURCING.value):
                lines_has_invalid_status.append(line)
    if lines_has_actual_gi_date:
        return {
            "status": False,
            "item_errors": [line.item_no for line in lines_has_actual_gi_date],
            "flag": "gidate"
        }
    if lines_has_invalid_status:
        return {
            "status": False,
            "item_errors": [line.item_no for line in lines_has_invalid_status],
            "flag": "status"
        }

    return {
        "status": True,
        "item_errors": [],
    }


def resolve_show_atp_ctp_popup_change_order(line_ids):
    lines = migration_models.OrderLines.objects.filter(id__in=line_ids)
    return get_atp_ctp_popup_response(lines)


def resolve_domestic_order_confirmation():
    return migration_models.Order.objects.filter(
        Q(distribution_channel_id=1)
        | Q(distribution_channel_id=2)
        | Q(distribution_channel_id=3)).all()


def resolve_enum(enum):
    status = [(key, val.value) for key, val in vars(enum).items() if not key.startswith("_")]
    return status


def resolve_order_confirmation_status():
    return resolve_enum(SapOrderConfirmationStatus)


def resolve_non_confirm_quantity(root):
    try:
        if root.quantity > root.assigned_quantity:
            rs = root.quantity - root.assigned_quantity
            return rs
    except:
        return None


def get_address_from_code(partner_code="", type="", info=None):
    try:
        sold_to_partner_address = master_models.SoldToPartnerAddressMaster.objects.filter(
            partner_code=partner_code
        ).first()
        name_fields = [
            "name1",
            "name2",
            "name3",
            "name4"
        ]
        address_fields = [
            "street",
            "street_sup1",
            "street_sup2",
            "street_sup3",
            "location",
            "district",
            "city",
            "postal_code"
        ]
        if info:
            if order_id := info.variable_values.get("id"):
                order = migration_models.Order.objects.filter(pk=order_id).first()
                if order.type == OrderType.DOMESTIC.value:
                    address_fields = [
                        "street",
                        "district",
                        "city",
                        "postal_code"
                    ]
        if type == "all":
            address_fields = name_fields + address_fields
        if type == "name":
            address_fields = name_fields
        # ignore empty string to avoid duplicate space
        address = " ".join(filter(None, [
            getattr(sold_to_partner_address, field, "") for field in address_fields
        ]))

        return address

    except Exception:
        return ""
def get_sold_to_address_from_code(sold_to_code, type="", info=None):
    try:
        sold_to_partner_address = get_sold_to_partner(sold_to_code)
        name_fields = [
            "name1",
            "name2",
            "name3",
            "name4"
        ]
        address_fields = [
            "street",
            "street_sup1",
            "street_sup2",
            "street_sup3",
            "location",
            "district",
            "city",
            "postal_code"
        ]
        if info:
            if order_id := info.variable_values.get("id"):
                order = migration_models.Order.objects.filter(pk=order_id).first()
                if order.type == OrderType.DOMESTIC.value:
                    address_fields = [
                        "street",
                        "district",
                        "city",
                        "postal_code"
                    ]
        if type == "all":
            address_fields = name_fields + address_fields
        if type == "name":
            address_fields = name_fields
        # ignore empty string to avoid duplicate space
        address = " ".join(filter(None, [
            getattr(sold_to_partner_address, field, "") for field in address_fields
        ]))

        return address

    except Exception:
        return ""

def call_sap_es08(root, info):
    try:
        sales_organization_code = root.sales_organization.code
        sold_to_code = root.sold_to.sold_to_code
        pi_message_id = str(time.time())
        body = {
            "piMessageId": pi_message_id,
            "customerId": sold_to_code,
            "saleOrg": sales_organization_code,
        }
        response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
            SapEnpoint.ES_08.value,
            body
        )
        data = response["data"][0]

        return data

    except Exception:
        return None


def resolve_ship_to_address(root, info):
    try:
        partner_code = get_code_from_ship_to_bill_to(remove_padding_zero_from_ship_to(root.contract.ship_to))
        ship_to_address = get_address_from_code(partner_code)

        if ship_to_address:
            return ship_to_address

        data = call_sap_es08(root, info)
        if data:
            result = list(filter(lambda item: item["partnerFunction"] == "WE", data["partnerList"]))
            ship_to_party = result[0]
            ship_to_address = get_address_from_code(ship_to_party.get("partnerNo"))

        return ship_to_address
    except Exception:
        return None


def resolve_sold_to_address(root, info):
    try:
        sold_to_code = root.sold_to.sold_to_code
        sold_to_address = get_sold_to_address_from_code(sold_to_code)

        if sold_to_address:
            return sold_to_address

        data = call_sap_es08(root, info)
        if data:
            sold_to_address = f"{data.get('street1')} " \
                              f"{data.get('district')} {data.get('city')} {data.get('postcode')}"

        return sold_to_address


    except Exception:
        return None


def resolve_bill_to_address(root, info):
    try:
        partner_code = get_code_from_ship_to_bill_to(root.contract.bill_to)
        bill_to_address = get_address_from_code(partner_code)

        if bill_to_address:
            return bill_to_address

        data = call_sap_es08(root, info)
        if data:
            result = list(filter(lambda item: item["partnerFunction"] == "RE", data["partnerList"]))
            bill_to_party = result[0]
            bill_to_address = get_address_from_code(bill_to_party.get("partnerNo"))

        return bill_to_address

    except Exception:
        return None


def resolve_sales_organization():
    return migration_models.SalesOrganizationMaster.objects.all()


def resolve_list_lms_report_cs_admin(data_filter, info):
    # data_return = {
    #     "delHeaderData": {
    #         "data": {
    #             "dpNo": "",
    #             "po_no": "",
    #             "item_no": "",
    #             "quantity": "",
    #             "soldTo": "",
    #             "gi_date_time": "",
    #             "car_registration_no": "",
    #             "departure_place_position": "",
    #             "estimate_date_time": "",
    #             "transportation_status": "",
    #             "current_position": "",
    #             "remaining_distance_as_kilometers": "",
    #             "estimated_arrival_date_and_time": "",
    #         }
    #     },
    #     "delItemData": {
    #         "itemData": {
    #             "saleUnit": "",
    #             "matDes": "",
    #             "soNo": "",
    #         }
    #     },
    #     "partnerData": {
    #         "data": {
    #             "partnerFunction": "",
    #             "shipTo": "",
    #             "addCode": "",
    #         }
    #     },
    #     "addressList": {
    #         "address": {
    #             "addNo": "",
    #             "shipToName": "",
    #             "addCode": "",
    #         }
    #     }
    #
    # }
    data_return = [
        {
            "dp_no": "416045436",
            "po_no": "122060062",
            "so_no": "1112343211",
            "item_no": "10",
            "material_description": "CA SUPPERFLUTE125D-Dia117N Mix 70%",
            "quantity": 100,
            "sale_unit": "ม้วน",
            "sold_to_code_name": "บจก เอสซีจี โลจิสติก",
            "ship_to_name": "บจก เอสซีจี โลจิสติก โกดัง A",
            "gi_date_time": "08/06/2022 18:43:07",
            "car_registration_no": "กท2462",
            "departure_place_position": "โกดังบ้านโป่ง",
            "estimate_date_time": "09/06/2022 12:00:00",
            "transportation_status": "เดินทางกลับจากลูกค้า",
            "current_position": "ราชบุรี",
            "remaining_distance_as_kilometers": "12",
            "estimated_arrival_date_and_time": "30-04-2022 02:44:22",
        },
        {
            "dp_no": "416045436",
            "po_no": "122060062",
            "so_no": "1112343211",
            "item_no": "10",
            "material_description": "CA SUPPERFLUTE125D-Dia117N Mix 70%",
            "quantity": 100,
            "sale_unit": "ม้วน",
            "sold_to_code_name": "บจก เอสซีจี โลจิสติก",
            "ship_to_name": "บจก เอสซีจี โลจิสติก โกดัง A",
            "gi_date_time": "08/06/2022 18:43:07",
            "car_registration_no": "กท2462",
            "departure_place_position": "โกดังบ้านโป่ง",
            "estimate_date_time": "09/06/2022 12:00:00",
            "transportation_status": "เดินทางกลับจากลูกค้า",
            "current_position": "ราชบุรี",
            "remaining_distance_as_kilometers": "12",
            "estimated_arrival_date_and_time": "30-04-2022 02:44:22",
        },
        {
            "dp_no": "416045436",
            "po_no": "122060062",
            "so_no": "1112343211",
            "item_no": "10",
            "material_description": "CA SUPPERFLUTE125D-Dia117N Mix 70%",
            "quantity": 100,
            "sale_unit": "ม้วน",
            "sold_to_code_name": "บจก เอสซีจี โลจิสติก",
            "ship_to_name": "บจก เอสซีจี โลจิสติก โกดัง A",
            "gi_date_time": "08/06/2022 18:43:07",
            "car_registration_no": "กท2462",
            "departure_place_position": "โกดังบ้านโป่ง",
            "estimate_date_time": "09/06/2022 12:00:00",
            "transportation_status": "เดินทางกลับจากลูกค้า",
            "current_position": "ราชบุรี",
            "remaining_distance_as_kilometers": "12",
            "estimated_arrival_date_and_time": "30-04-2022 02:44:22",
        },
        {
            "dp_no": "416045436",
            "po_no": "122060062",
            "so_no": "1112343211",
            "item_no": "10",
            "material_description": "CA SUPPERFLUTE125D-Dia117N Mix 70%",
            "quantity": 100,
            "sale_unit": "ม้วน",
            "sold_to_code_name": "บจก เอสซีจี โลจิสติก",
            "ship_to_name": "บจก เอสซีจี โลจิสติก โกดัง A",
            "gi_date_time": "08/06/2022 18:43:07",
            "car_registration_no": "กท2462",
            "departure_place_position": "โกดังบ้านโป่ง",
            "estimate_date_time": "09/06/2022 12:00:00",
            "transportation_status": "เดินทางกลับจากลูกค้า",
            "current_position": "ราชบุรี",
            "remaining_distance_as_kilometers": "12",
            "estimated_arrival_date_and_time": "30-04-2022 02:44:22",
        },
        {
            "dp_no": "416045436",
            "po_no": "122060062",
            "so_no": "1112343211",
            "item_no": "10",
            "material_description": "CA SUPPERFLUTE125D-Dia117N Mix 70%",
            "quantity": 100,
            "sale_unit": "ม้วน",
            "sold_to_code_name": "บจก เอสซีจี โลจิสติก",
            "ship_to_name": "บจก เอสซีจี โลจิสติก โกดัง A",
            "gi_date_time": "08/06/2022 18:43:07",
            "car_registration_no": "กท2462",
            "departure_place_position": "โกดังบ้านโป่ง",
            "estimate_date_time": "09/06/2022 12:00:00",
            "transportation_status": "เดินทางกลับจากลูกค้า",
            "current_position": "ราชบุรี",
            "remaining_distance_as_kilometers": "12",
            "estimated_arrival_date_and_time": "30-04-2022 02:44:22",
        },
    ]
    return data_return


def resolve_get_gps_tracking(gps_tracking, info):
    data_return = {
        "shipment_no": "0410123850",
        "car_registration_no": "70-5800 กจ",
        "current_position": "ราชบุรี",
        "carrier": "ปกรณ์ทรานสปอร์ต",
        "speed": 110,
        "date_and_time_of_the_last_signal_received": "28/10/2022 18:03:45",
        "payment_no": "0416045436",
        "place_of_delivery": "บจก. เอสซีจี โลจิสติก",
        "car_status": "เดินทางกลับจากลูกค้า",
        "destination_reach_time": "12:00:00",
        "estimate_to_customers_from_their_current_location": "12:00:00",
        "approximate_remaining_distance": 100,
        "estimated_time": "3",
        "estimated_arrival_time": "12:00:00",
        "distance_from_factory_to_customer": 120,
        "date_of_issuance_of_invoice": "28/10/2022",
        "delivery_deadline": "29/10/2022 12:00:00",
    }

    return data_return


def resolve_get_dp_hyperlink(dp_no, info):
    data_return = [
        {
            "dp_no": "416045436",
            "po_no": "122060062",
            "so_no": "1112343211",
            "item_no": "10",
            "material_description": "CA SUPPERFLUTE125D-Dia117N Mix 70%",
            "quantity": 100,
            "sale_unit": "ม้วน",
        },
        {
            "dp_no": "416045436",
            "po_no": "122060062",
            "so_no": "1112343211",
            "item_no": "10",
            "material_description": "CA SUPPERFLUTE125D-Dia117N Mix 70%",
            "quantity": 100,
            "sale_unit": "ม้วน",
        },
        {
            "dp_no": "416045436",
            "po_no": "122060062",
            "so_no": "1112343211",
            "item_no": "10",
            "material_description": "CA SUPPERFLUTE125D-Dia117N Mix 70%",
            "quantity": 100,
            "sale_unit": "ม้วน",
        },
        {
            "dp_no": "416045436",
            "po_no": "122060062",
            "so_no": "1112343211",
            "item_no": "10",
            "material_description": "CA SUPPERFLUTE125D-Dia117N Mix 70%",
            "quantity": 100,
            "sale_unit": "ม้วน",
        }
    ]
    total_quantity = 0
    for data in data_return:
        total_quantity += data["quantity"]
    response = {
        "total_quantity": total_quantity,
        "dp_no_lines": data_return,
    }

    return response


def resolve_description_en_preview_order(variant_code):
    try:
        material = master_models.MaterialMaster.objects.filter(material_code=variant_code).first()
        return material.description_en
    except:
        return None


def call_sap_es26(so_no, *args, order_id=None, **kwargs):
    params = {
        "piMessageId": str(uuid.uuid1().int),
        "saleOrderNo": so_no
    }
    log_val = {
        "order_number": so_no,
        "orderid": order_id,
    }
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value, **log_val).request_mulesoft_get(
        SapEnpoint.ES_26.value,
        params
    )

    return response


def get_code_from_ship_to_bill_to(data):
    code = data.split(" - ")[0]
    return code.strip()


def resolve_sap_change_order(input_data, info):
    manager = info.context.plugins
    params = prepare_param_for_es25(input_data, get_order_line=True)
    api_response = call_es25_and_get_response(params, manager)
    data = api_response.get('data')
    data_items_from_api = api_response.get("dataItem", [])
    if not data or not data_items_from_api:
        return []
    add_is_not_ref_to_es_25_res(data, data_items_from_api)
    return from_api_response_es25_to_change_order(data, input_data)


def make_order_line_list_oder_confirmation(order, line, status_input):
    rt = []
    list_status = get_list_status_from_es25_data_item(line)
    if status_input in list_status:
        list_status = [status_input]
    for status in list_status:
        if status_input is SapOrderConfirmationStatusParam.CONFIRM and status != SapOrderConfirmationStatusParam.CONFIRM:
            continue
        elif status_input is SapOrderConfirmationStatusParam.NON_CONFIRM and status != SapOrderConfirmationStatusParam.NON_CONFIRM:
            continue
        elif status_input is SapOrderConfirmationStatusParam.REJECT and status != SapOrderConfirmationStatusParam.REJECT:
            continue
        formatted_values = {}

        if line.get("saleUnit") and SalesUnitEnum.is_qty_conversion_to_decimal(
                line.get("saleUnit")
        ):
            formatted_values.update({
                "orderQty": format_sap_decimal_values_for_report(line.get("orderQty", 0)),
                "confirmQty": format_sap_decimal_values_for_report(line.get("confirmQty", 0)),
                "nonConfirmQty": format_sap_decimal_values_for_report(line.get("nonConfirmQty", 0))
            })
        else:
            formatted_values.update({
                "orderQty": line.get("orderQty", 0),
                "confirmQty": line.get("confirmQty", 0),
                "nonConfirmQty": line.get("nonConfirmQty", 0)
            })
        rt.append({
            "sale_org": order.get("salesOrg", ""),
            "sold_to_code": order.get("soldTo", ""),
            "sold_to_name": order.get("soldToName1", ""),
            "item_no": line.get("itemNo", "").lstrip("0"),
            "material_code": line.get("matNo", ""),
            "material_description": line.get("matDesc", ""),
            "order_qty": formatted_values.get("orderQty"),
            "confirm_quantity": formatted_values.get("confirmQty"),
            "non_confirm_quantity": formatted_values.get("nonConfirmQty"),
            "sale_unit": line.get("saleUnit", ""),
            "request_date": line.get("shiptToPODate", ""),
            "confirm_date": line.get("firstDeliveryDT", ""),
            "status": SapOrderConfirmationStatusParam.MAPPING_TO_TEXT[status],
            "remark_order": line.get("remarkOrder") or ""
        })
    return rt


def mapping_data_item_from_es25_response(data, data_item):
    new_data = {item['sdDoc']: item for item in data}
    for item in data_item:
        item.update({"data": new_data.get(item.get("sdDoc"))})
    return data_item


def custom_key(order_line: OrderLines):
    so_no = order_line.order.so_no
    item_no = order_line.item_no
    return f'{so_no}_{item_no}'


def mapping_data_from_result(data):
    # group line by so_no
    so_no_to_rs = {}
    for item in data:
        so_no = item["so_no"]
        if so_no not in so_no_to_rs:
            so_no_to_rs[so_no] = item
            continue

        if order_lines := item["order_lines"]:
            so_no_to_rs[so_no]["order_lines"] += order_lines

    rs = list(so_no_to_rs.values())

    # sort by status
    for item in rs:
        sort_order_confirmation_data_item_by_status(item["order_lines"])

    return rs


def resolve_list_order_confirmation_sap(input_data, info):
    params = prepare_param_for_es25_order_confirmation(input_data)
    api_response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
        SapEnpoint.ES_25.value,
        params
    )
    res = []

    data = api_response.get("data", [])
    if not data:
        return []
    data_item = api_response.get("dataItem", [])
    if not data or not data_item:
        return []
    add_is_not_ref_to_es_25_res(data, data_item)
    mapped_rs = mapping_data_item_from_es25_response(data, data_item)
    sale_org_code_to_org_short_name = get_sale_org_code_to_org_short_name(
        [order_res.get("salesOrg") for order_res in data])

    for rs in mapped_rs:
        order = rs["data"]
        so_no = order.get("sdDoc", "")
        po_no = order.get("poNo", "")
        order_date = order.get("createDate", "")
        sales_org_name = sale_org_code_to_org_short_name.get(str(order.get("salesOrg"))) or ""
        sold_to_name = order.get("soldToName1", "")
        payment_term = order.get("paymentTerm", "")
        payment_term_mapping = PAYMENT_TERM_MAPPING.get(order.get("paymentTerm", ""), order.get("paymentTermDesc", ""))
        payment_method_name = f"{payment_term} - {payment_term_mapping}"
        ship_to_code = order.get("shipTo") or ""
        contract_no = order.get("contractNo", "")
        contract_name = order.get("descriptionInContract", "")
        rs_line = {
            "so_no": so_no,
            "po_no": po_no,
            "order_date": order_date,
            "sales_org_name": sales_org_name,
            "sold_to_name": sold_to_name,
            "payment_method_name": payment_method_name,
            "contract_no": contract_no,
            "order_lines": [],
            "contract_name": contract_name,
            "ship_to_code": ship_to_code,
            "is_not_ref": order.get("is_not_ref", False)
        }
        lines = make_order_line_list_oder_confirmation(order, rs, input_data.get("status"))
        rs_line["order_lines"].extend(lines)
        res.append(rs_line)

    result_final = mapping_data_from_result(res)

    return result_final


def get_sale_org_code_to_org_short_name(org_codes):
    rows = master_models.SalesOrganizationMaster.objects.filter(
        code__in=org_codes
    ).only("code", "short_name").values()
    code_to_row = {row["code"]: row["short_name"] for row in rows}
    return code_to_row


def get_sold_to_name(sold_to_code):
    try:
        sold_to = master_models.SoldToMaster.objects.filter(
            sold_to_code=sold_to_code
        ).first()
        return sold_to.sold_to_name
    except Exception:
        return None


def get_formatted_address_option_text(partner_code):
    try:
        sold_to_partner_address = master_models.SoldToPartnerAddressMaster.objects.filter(
            partner_code=partner_code
        ).first()

        name_fields = ["name1", "name2", "name3", "name4"]
        address_fields = ["street", "street_sup1", "street_sup2", "street_sup3", "location", "district", "city",
                          "postal_code"]

        partner_name_text = "".join(
            [getattr(sold_to_partner_address, field) for field in name_fields if
             getattr(sold_to_partner_address, field)]
        )
        location_text = " ".join(
            [getattr(sold_to_partner_address, field) for field in address_fields if
             getattr(sold_to_partner_address, field)]
        )

        return f"{partner_code} - {partner_name_text}\n{location_text}"

    except Exception as e:
        logger.exception(str(e))
        return ""


def resolve_allow_change_inquiry_method(order_line):
    return is_allow_to_change_inquiry_method(order_line)


def resolve_get_lms_report_cs_customer(info, data_filter):
    response = call_api_get_lms_report(data_filter=data_filter, sap_fn=info.context.plugins.call_api_sap_client,
                                       info=info)
    info.variable_values.update({"lms_report_response": response})
    return response


def resolve_get_gps_report_cs_customer(info, data_filter):
    response = call_api_get_gps_report(data_filter=data_filter, sap_fn=info.context.plugins.call_api_sap_client,
                                       info=info)
    info.variable_values.update({"lms_report_response": response})
    return response


def call_api_get_lms_report(data_filter, sap_fn, info):
    params = prepare_param_for_api_get_lms_report(data_filter, info)
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_get(
        SapEnpoint.LMS_REPORT.value,
        params
    )
    return response


def call_api_get_gps_report(data_filter, sap_fn, info):
    params = prepare_param_for_api_get_gps_report(data_filter, info)
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
        SapEnpoint.LMS_REPORT_GPS.value,
        params
    )
    return response


def build_ship_to_party(order, info):
    def _get_ship_to_att(root, info):
        partner_code = get_code_from_ship_to_bill_to(remove_padding_zero_from_ship_to(order.contract.ship_to))
        ship_to_names = get_address_from_code(partner_code, type="name")
        ship_to_address = get_address_from_code(partner_code)

        if ship_to_names:
            return partner_code, ship_to_names, ship_to_address

        data = call_sap_es08(order, info)
        if data:
            result = list(filter(lambda item: item["partnerFunction"] == "WE", data["partnerList"]))
            ship_to_party = result[0]
            partner_code = ship_to_party.get("partnerNo")
            ship_to_names = get_address_from_code(partner_code, type='all')
            ship_to_address = get_address_from_code(partner_code)

        return partner_code, ship_to_names, ship_to_address
    try:
        partner_code, ship_to_names, ship_to_address = _get_ship_to_att(order, info)
        return f'{remove_padding_zero_from_ship_to(partner_code)} - {ship_to_names}\n{ship_to_address}'
    except Exception:
        return None
