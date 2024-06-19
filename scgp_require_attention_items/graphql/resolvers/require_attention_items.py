import uuid
from datetime import datetime

from django.db.models import (
    Q,
    Subquery,
    Value
)
from django.db.models.functions import Concat

from common.enum import MulesoftServiceType
from common.helpers import add_is_not_ref_to_es_25_res
from common.mulesoft_api import MulesoftApiRequest
from scgp_cip.api_examples.es_25_response import ES25_SAMPLE_RESPONSE1
from scgp_cip.common.constants import OTC_ACCOUNT_GROUPS
from scgp_cip.dao.order.sold_to_master_repo import SoldToMasterRepo
from scgp_cip.service.helper.order_line_helper import separate_parent_and_bom_order_lines, \
    sorted_and_merged_order_line_list
from scgp_cip.service.ots_service import extract_and_map_ots_response_to_sap_response, prepare_payload_and_call_ots
from scgp_export.graphql.enums import SapEnpoint
from scgp_export.graphql.resolvers.export_sold_tos import resolve_display_text, resolve_sold_to_name
from scgp_require_attention_items.graphql.enums import (
    ScgpRequireAttentionItemStatus,
    ScgpRequireAttentionType,
    ScgpRequireAttentionConsignment,
    ScgpRequireAttentionSplitOrderItemPartialDelivery,
    ScgpRequireAttentionTypeOfDelivery,
    ChangeOrderOrderStatus,
)

from sap_migration import models as sap_migrations_models
from sap_master_data import models as sap_master_data_models
from scgp_require_attention_items.graphql.helper import (
    convert_to_ton,
    prepare_param_for_es25,
    make_list_order_line_for_sap_order_line,
    make_summary_for_sold_to_from_order_line_in_es25,
    prepare_param_for_es25_order_pending,
    make_excel_from_list_of_sale_order_sap,
    get_sold_to_from_order_line,
    get_order_from_order_line,
    get_material_from_order_line,
    get_material_variant_from_order_line,
    get_sales_organization_from_order_line,
    get_sales_group_from_order_line,
    get_i_plan_from_order_line,
    get_order_line_from_order_line_iplan, mapping_material_group1,
    format_item_no, derive_parent_price_and_weight_for_bom, group_otc_orders, group_items_by_sold_to,
    set_default_quantity_to_es25_response, remove_parent_item_no_for_child_search
)
from utils.enums import IPlanInquiryMethodCode


def resolve_require_attention_enum(enum):
    status = [(key, val.value) for key, val in vars(enum).items() if not key.startswith("_")]
    return status


def resolve_filter_require_attention_view_all():
    return sap_migrations_models.OrderLines.objects.filter(attention_type__icontains="R").exclude(
        Q(order__status__in=["draft", "confirmed"])
    ).all()


def resolve_order_lines_all():
    return sap_migrations_models.OrderLines.objects.all()


def resolve_customer_contract_all():
    return sap_migrations_models.Contract.objects.all()


def resolve_filter_require_attention_view_by_role(role):
    qs = sap_migrations_models.OrderLines.objects.filter(attention_type__icontains="R").exclude(
        order__status__in=["draft", "confirmed"]
    ).exclude(
        status__in=["Disable", "Delete", ""]
    ).prefetch_related("order", "order__contract", "order__contract__sold_to", "order__sales_organization", "material",
                       "iplan", "order__sales_group", "order__scgp_sales_employee").all()
    if role == "Domestic":
        return qs.filter(Q(order__distribution_channel__code=10)
                         | Q(order__distribution_channel__code=20))
    elif role == "Export":
        return qs.filter(Q(order__distribution_channel__code=30))


def resolve_filter_require_attention_sold_to():
    return sap_master_data_models.SoldToMaster.objects.all()


def resolve_filter_require_attention_sale_employee():
    return sap_migrations_models.Order.objects.all()


def resolve_filter_require_attention_material_group():
    return sap_master_data_models.ScgpMaterialGroup.objects.all()


def resolve_filter_require_attention_material():
    return sap_master_data_models.MaterialClassificationMaster.objects.all()


def resolve_filter_require_attention_sales_organization():
    return sap_master_data_models.SalesOrganizationMaster.objects.all()


def resolve_filter_require_attention_business_unit():
    return sap_migrations_models.BusinessUnits.objects.all()


def resolve_filter_require_attention_sales_group():
    return sap_migrations_models.SalesGroupMaster.objects.all()


def resolve_require_attention_item_status():
    return resolve_require_attention_enum(ScgpRequireAttentionItemStatus)


def resolve_require_attention_type():
    return resolve_require_attention_enum(ScgpRequireAttentionType)


def resolve_require_attention_by_unique_id(order_line_id):
    return sap_migrations_models.OrderLineIPlan.objects.filter(orderlines__id=order_line_id).first()


def resolve_require_attention_items_i_plan(order_line_id):
    return sap_migrations_models.OrderLineIPlan.objects.filter(orderlines__id=order_line_id).first()


def resolve_order_no(order_line):
    order = getattr(order_line, 'order', None)
    return getattr(order, 'so_no', None)


def resolve_sold_to(order_line):
    sold_to = get_sold_to_from_order_line(order_line)
    sold_to_name = ""
    sold_to_code = getattr(sold_to, "sold_to_code", "")
    if sold_to_code:
        sold_to_name = resolve_sold_to_name(sold_to_code)
    return (sold_to_code + " - " + sold_to_name) or ""


def resolve_status(order_line):
    order = get_order_from_order_line(order_line)
    status = getattr(order, 'status', None)
    if status and status == ChangeOrderOrderStatus.CANCELLED.value:
        status = "Cancelled"
    return status


def resolve_unit(order_line):
    material = get_material_from_order_line(order_line)
    return getattr(material, 'sales_unit', "")


def resolve_material(order_line):
    material = get_material_from_order_line(order_line)
    return getattr(material, 'name', "")


def get_order_line_and_type(order_line_id):
    try:
        order_line = sap_migrations_models.OrderLines.objects.filter(id=order_line_id).first()
        return order_line, order_line.type
    except AttributeError:
        raise ValueError("Do not have this order line or this order line missing type")


def resolve_mat_description(order_line):
    material_variant = get_material_variant_from_order_line(order_line)
    return getattr(material_variant, 'description_th', None)


def resolve_grade(order_line_id):
    try:
        order_line, _ = get_order_line_and_type(order_line_id)
        return sap_master_data_models.MaterialClassificationMaster.objects.filter(
            material=order_line.material_variant.material).first().grade
    except AttributeError:
        return None


def resolve_gram(order_line_id):
    try:
        order_line, _ = get_order_line_and_type(order_line_id)
        return sap_master_data_models.MaterialClassificationMaster.objects.filter(
            material=order_line.material_variant.material).first().basis_weight
    except AttributeError:
        return None


def resolve_filter_require_attention_view_by_ids(ids):
    return sap_migrations_models.OrderLines.objects.filter(
        id__in=ids,
        actual_gi_date__isnull=True
    ).exclude(order__status__in=["draft", "confirmed"])


def resolve_filter_require_attention_edit_items_by_ids(ids):
    return sap_migrations_models.OrderLines.objects.filter(
        id__in=ids,
    ).exclude(order__status__in=["draft", "confirmed", "failed_confirm"])


def resolve_mat_code(order_line):
    material_variant = get_material_variant_from_order_line(order_line)
    return getattr(material_variant, 'code', "")


def resolve_require_attention_inquiry_method_code():
    return resolve_require_attention_enum(IPlanInquiryMethodCode)


def resolve_require_attention_type_of_delivery():
    return resolve_require_attention_enum(ScgpRequireAttentionTypeOfDelivery)


def resolve_require_attention_split_order_item_partial_delivery():
    return resolve_require_attention_enum(ScgpRequireAttentionSplitOrderItemPartialDelivery)


def resolve_require_attention_consignment():
    return resolve_require_attention_enum(ScgpRequireAttentionConsignment)


def resolve_consignment_value(consignment):
    consignment_dict = {
        "1000 - Free Stock": "FREE_STOCK_1000",
        "1001 - Free Stock": "FREE_STOCK_1001",
        "1002 - Free Stock": "FREE_STOCK_1002",
    }
    return consignment_dict.get(consignment)


def resolve_type_of_delivery_value(type_of_delivery):
    type_of_delivery_dict = {
        "Arrival": "ARRIVAL",
        "Ex-mill": "EX_MILL"
    }
    return type_of_delivery_dict.get(type_of_delivery)


def resolve_partial_delivery_split_order_value(partial_delivery):
    partial_delivery_split_order_dict = {
        "Yes": "YES",
        "No": "NO"
    }
    return partial_delivery_split_order_dict.get(partial_delivery)


def resolve_sales_organization(order_line):
    order = get_order_from_order_line(order_line)
    return getattr(order, 'sales_organization', None)


def resolve_sales_group(order_line):
    sales_group = get_sales_group_from_order_line(order_line)
    return getattr(sales_group, 'code', None)


def resolve_scgp_sales_employee(order_line):
    order = get_order_from_order_line(order_line)
    return getattr(order, 'scgp_sales_employee', None)


def resolve_request_quantity(order_line):
    return getattr(order_line, 'quantity', 0)


def resolve_material_group_from_material_classification_master(material_classification_master):
    return getattr(material_classification_master, 'material', None)


def resolve_gram_from_material_classification_master(material_classification_master):
    return getattr(material_classification_master, 'basis_weight', None)


def resolve_code_from_material_classification_master(material_classification_master):
    return getattr(material_classification_master, 'material_code', None)


def resolve_name_from_material_classification_master(material_classification_master):
    material = getattr(material_classification_master, 'material', None)
    return getattr(material, 'description_th', "")


def resolve_code_from_sold_to_master(sold_to):
    return getattr(sold_to, 'sold_to_code', None)


def resolve_name_from_sold_to_master(sold_to):
    return getattr(sold_to, 'sold_to_name', None)


def resolve_items_from_order_line_i_plan(order_line_i_plan):
    return get_order_line_from_order_line_iplan(order_line_i_plan)


def resolve_material_group(order_line):
    return getattr(order_line, 'material', None)


def resolve_iplant_confirm_quantity_from_order_line(order_line):
    iplan = getattr(order_line, 'iplan', None)
    return getattr(iplan, 'iplant_confirm_quantity', None)


def resolve_item_status_from_order_line(order_line):
    return getattr(order_line, 'item_status_en', None)


def resolve_original_date_from_order_line(order_line):
    return getattr(order_line, 'original_request_date', None)


def resolve_inquiry_method_code_from_order_line(order_line):
    return getattr(order_line, 'inquiry_method', None)


def resolve_transportation_method_code_from_order_line(order_line):
    iplan = get_i_plan_from_order_line(order_line)
    return getattr(iplan, 'transportation_method', None)


def resolve_type_of_delivery_from_order_line(order_line):
    iplan = get_i_plan_from_order_line(order_line)
    return getattr(iplan, 'type_of_delivery', None)


def resolve_fix_source_assignment_from_order_line(order_line):
    iplan = get_i_plan_from_order_line(order_line)
    return getattr(iplan, 'fix_source_assignment', None)


def resolve_split_order_item_from_order_line(order_line):
    iplan = get_i_plan_from_order_line(order_line)
    return getattr(iplan, 'split_order_item', None)


def resolve_partial_delivery_from_order_line(order_line):
    iplan = get_i_plan_from_order_line(order_line)
    return getattr(iplan, 'partial_delivery', None)


def resolve_consignment_from_order_line(order_line):
    iplan = get_i_plan_from_order_line(order_line)
    return getattr(iplan, 'consignment', None)


def resolve_code_from_material_master(material_master):
    return getattr(material_master, 'material_code', None)


def resolve_name_from_material_master(material_master):
    return getattr(material_master, 'name', None)


def resolve_overdue_1_from_order_line_i_plan(order_line_i_plan):
    order_line = get_order_line_from_order_line_iplan(order_line_i_plan)
    return getattr(order_line, 'overdue_1', None)


def resolve_overdue_2_from_order_line_i_plan(order_line_i_plan):
    order_line = get_order_line_from_order_line_iplan(order_line_i_plan)
    return getattr(order_line, 'overdue_2', None)


def resolve_po_no(order_line):
    order = get_order_from_order_line(order_line)
    return getattr(order, 'po_no', None)


def resolve_sales_unit(iplan):
    order_line = get_order_line_from_order_line_iplan(iplan)
    material = get_material_from_order_line(order_line)
    return getattr(material, 'base_unit', "")


def resolve_order_id(order_line):
    return getattr(order_line, 'order_line', None)


def resolve_ship_to(order_line):
    if order_line.order.type == "export":
        return getattr(order_line.order, 'ship_to', None)
    return getattr(order_line, 'ship_to', None)


def resolve_filter_require_attention_material_variant_master():
    return sap_migrations_models.MaterialVariantMaster.objects.all()


def resolve_filter_require_attention_material_master(qs):
    return sap_migrations_models.MaterialMaster.objects.filter(material_code__in=qs).exclude(delete_flag="X")


def resolve_material_sale_master_distinct_on_material_group_1():
    return sap_master_data_models.MaterialSaleMaster.objects \
        .exclude(Q(material_group1__isnull=True) | Q(material_group1__regex=r'^\s*$')) \
        .order_by('material_group1') \
        .distinct('material_group1')


def resolve_material_sale_master_distinct_on_distribution_channel(distribution_channel_code):
    return sap_master_data_models.MaterialSaleMaster.objects.filter(
        distribution_channel_code__in=distribution_channel_code).values('material_code')


def resolve_sales_order(sold_to_id):
    return sap_migrations_models.OrderLines.objects.filter(order__contract__sold_to_id=sold_to_id)


def resolve_require_attention_flag(order_line):
    return getattr(order_line, 'attention_type', None)


def resolve_create_by(order_line):
    order = get_order_from_order_line(order_line)
    created_by = getattr(order, 'created_by', None)
    return getattr(created_by, 'first_name', "") + ' - ' + getattr(created_by, 'last_name', "")


def resolve_create_date_time(order_line):
    order = get_order_from_order_line(order_line)
    return getattr(order, 'created_at', None)


def resolve_create_date(order_line):
    return resolve_create_date_time(order_line)


def resolve_req_delivery_date(order_line):
    order = get_order_from_order_line(order_line)
    return getattr(order, 'request_delivery_date', None)


def resolve_confirm_date(order_line):
    return getattr(order_line, 'confirmed_date', None)


def resolve_order_item(order_line):
    return getattr(order_line, 'item_no', None)


def resolve_rejection(order_line):
    return getattr(order_line, 'reject_reason', None)


def resolve_delivery_block(order_line):
    order = get_order_from_order_line(order_line)
    return getattr(order, 'delivery_block', None)


def resolve_sales_org(order_line):
    sales_org = get_sales_organization_from_order_line(order_line)
    return sales_org.code + ' - ' + sales_org.name


def resolve_unit_sales_order(order_line):
    material = get_material_from_order_line(order_line)
    return getattr(material, 'base_unit', None)


def resolve_weight_unit(order_line):
    material = get_material_from_order_line(order_line)
    return getattr(material, 'weight_unit', None)


def resolve_currency(order_line):
    order = get_order_from_order_line(order_line)
    currency = getattr(order, 'currency', None)
    return getattr(currency, 'code', None)


def resolve_material_code_description(order_line):
    material_variant = get_material_variant_from_order_line(order_line)
    return getattr(material_variant, "code", "") + ' - ' + getattr(material_variant, "name", "")


def resolve_sale_order_material_code(order_line):
    material_variant = get_material_variant_from_order_line(order_line)
    return getattr(material_variant, 'code', None)


def resolve_material_pricing_group_distinct():
    return sap_migrations_models.OrderLines.objects.filter(pk__in=Subquery(
        sap_migrations_models.OrderLines.objects.exclude(material_pricing_group__isnull=True).exclude(
            material_pricing_group__iexact="").distinct(
            'material_pricing_group').values('pk')
    ))


def resolve_list_order_type_distinct():
    return sap_migrations_models.Order.objects.filter(pk__in=Subquery(
        sap_migrations_models.Order.objects.exclude(order_type__isnull=True).exclude(
            order_type__iexact="").distinct(
            'order_type').values('pk')
    ))


def resolve_item_status_from_order_line_i_plan(order_line_i_plan):
    order_line = get_order_line_from_order_line_iplan(order_line_i_plan)
    return getattr(order_line, 'item_status_en', None)


def resolve_inquiry_method_code_from_order_line_i_plan(order_line_i_plan):
    order_line = get_order_line_from_order_line_iplan(order_line_i_plan)
    return getattr(order_line, 'inquiry_method', None)


def resolve_delivery_qty(order_line):
    return getattr(order_line, 'delivery_qty', 0)


def resolve_weight_sale_order(order_line_id, attribute):
    try:
        order_line = sap_migrations_models.OrderLines.objects.filter(id=order_line_id).first()
        quantity = getattr(order_line, attribute) if getattr(order_line, attribute) else 0
        weight_unit = order_line.material_variant.material.weight_unit
        material_code = order_line.material_variant.material.material_code
        return convert_to_ton(quantity, weight_unit, material_code)
    except Exception:
        return 0


def resolve_all_suggestion_search_for_material_grade_gram():
    mate = sap_migrations_models.MaterialVariantMaster.objects.exclude(material__delete_flag="X")
    return mate


def list_empty_sold_to_master():
    return sap_master_data_models.SoldToMaster.objects.filter(id__in=[])


def resolve_suggestion_search_sold_to_report_order_pending():
    ps = sap_master_data_models.SoldToMaster.objects.all()
    return ps


def resolve_suggestion_search_sales_organization_report_order_pending():
    return sap_master_data_models.SalesOrganizationMaster.objects.all()


def resolve_suggestion_search_material_no_grade_gram_report_order_pending(kwargs):
    material_grade_gram = kwargs.get("material_grade_gram")
    qs = sap_migrations_models.MaterialVariantMaster.objects.exclude(material__delete_flag="X")

    if material_grade_gram:
        filter_type = qs.annotate(search_text=Concat('code', Value(' - '), 'description_th')).filter(
            search_text__iexact=material_grade_gram).first().type
        qs = qs.filter(type=filter_type)
    return qs


def call_es08_get_list_sold_to_patty(info, sold_to_codes):
    manager = info.context.plugins
    default_data = {}
    query_data = sap_master_data_models.SoldToChannelPartnerMaster.objects \
        .filter(sold_to_code__in=sold_to_codes, partner_role='WE') \
        .distinct("sold_to_code", "sales_organization_code", "distribution_channel_code", "division_code") \
        .values_list("sold_to_code", "sales_organization_code", "distribution_channel_code", "division_code")

    ship_to_list = []
    for sold_to_code, sale_org, distribution_code, division_code in query_data:
        body = {
            "piMessageId": str(uuid.uuid1().int),
            "customerId": sold_to_code,
            "saleOrg": sale_org,
            "distriChannel": distribution_code,
            "division": division_code
        }

        response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
            SapEnpoint.ES_08.value,
            body
        )
        data = response.get('data', {})
        data = data[0] if len(data) else {}
        partner_list = data.get('partnerList', [])
        ship_to_list.extend(partner_list)
    ship_to_list = list(filter(lambda x:
                               x.get('partnerFunctionDes', "") == "Ship-to party" and \
                               x.get('partnerFunction', "") == 'WE',
                               ship_to_list))
    return ship_to_list


def mapping_new_data(instance: dict):
    sale_org = str(instance.get("saleOrg", ""))
    distribution_channel = str(instance.get("distributionChannel", ""))
    division = str(instance.get("division", ""))
    partner_function = str(instance.get("partnerFunction", ""))
    partner_no = str(instance.get("partnerNo", ""))

    search_text = f'{sale_org}-{distribution_channel}-{division}-{partner_function}-{partner_no}'
    return {'search_text': search_text, **instance}


def resolve_suggestion_search_ship_to_report_order_pending_data(info, kwargs):
    sold_to_codes = kwargs.get("sold_to_code", [])
    if not sold_to_codes:
        return []
    ship_to_list = call_es08_get_list_sold_to_patty(info, sold_to_codes)
    new_data_search = {ship_to['search_text']: ship_to for ship_to in list(map(mapping_new_data, ship_to_list))}
    ship_to_address_list = sap_master_data_models.SoldToChannelPartnerMaster.objects \
        .annotate(search_text=Concat('sales_organization_code', Value('-'),
                                     'distribution_channel_code', Value('-'),
                                     'division_code', Value('-'),
                                     'partner_role', Value('-'),
                                     'partner_code')). \
        distinct("search_text"). \
        filter(search_text__in=new_data_search.keys())

    ship_to_address_list = ship_to_address_list.values('address_link', 'search_text')
    list_partner_code_not_in_db = set([x['partnerNo'] for x in ship_to_list])
    address_list = {x['address_link']: x for x in ship_to_address_list}
    address_object = sap_master_data_models.SoldToPartnerAddressMaster.objects. \
        filter(address_code__in=address_list.keys()).distinct('partner_code')
    new_data = []
    set_name = set()

    for address in address_object:
        ship_object = address_list.get(address.address_code, {})
        if not ship_object:
            continue
        origin_data = new_data_search.get(ship_object['search_text'])
        address = get_address_name_from_partner_address(address)
        data = f"{address.get('name', '')}\n{address.get('address', '')}"
        if data not in set_name:
            new_data.append({"name": data, "code": origin_data['partnerNo']})
            set_name.add(data)
            list_partner_code_not_in_db.remove(origin_data['partnerNo'])
    list_partner_code_not_in_db = [{"name": "", "code": x} for x in list_partner_code_not_in_db]
    new_data.extend(list_partner_code_not_in_db)
    return new_data


def mapping_so_no_with_item_no(input_list_dict):
    result = {}
    for pair in input_list_dict:
        so_no = pair.get('order__so_no')
        if so_no not in result:
            result[so_no] = []
        result[so_no].append(pair.get('item_no').lstrip('0'))
    return result


def check_so_no_and_item_no_meet_the_condition(order_line, dict_so_no_with_item_no):
    so_no = order_line.get('sdDoc')
    if so_no in dict_so_no_with_item_no and order_line.get('itemNo').lstrip('0') in dict_so_no_with_item_no[so_no]:
        return True
    return False


def filter_sales_order_in_database(list_order_line_of_sold_to, mapping_order_with_order_lines, input_data):
    attention_type = input_data.get('require_attention_flag')
    if attention_type == 'ALL':
        attention_type = ""

    list_so_no = []
    for so_no, order in mapping_order_with_order_lines.items():
        list_so_no.append(so_no)
    kwargs_filter = Q(**{'order__so_no__in': list_so_no})

    if attention_type:
        kwargs_filter &= Q(**{'attention_type__icontains': attention_type})
        list_so_no_and_item_no = sap_migrations_models.OrderLines.objects.filter(kwargs_filter).exclude(
            item_no__iexact='').exclude(item_no__isnull=True).values('order__so_no', 'item_no')

        dict_so_no_with_item_no = mapping_so_no_with_item_no(list_so_no_and_item_no)
        list_order_line_of_sold_to = [order_line for order_line in list_order_line_of_sold_to if
                                      check_so_no_and_item_no_meet_the_condition(order_line, dict_so_no_with_item_no)]
        return list_order_line_of_sold_to
    else:
        list_order_line_of_sold_to = [order_line for order_line in list_order_line_of_sold_to]
        return list_order_line_of_sold_to


def call_es25_and_get_response(params, manager):
    return MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
        SapEnpoint.ES_25.value,
        params
    )


def check_sales_order_need_to_filter_in_database(input_data):
    return input_data.get('require_attention_flag') or input_data.get('create_by') or input_data.get(
        'request_delivery_date')


def resolve_list_of_sale_order_sap(input_data, info):
    delivery_block_input = input_data.get('delivery_block')
    params = prepare_param_for_es25(input_data, get_order_line=True)
    manager = info.context.plugins
    api_response = call_es25_and_get_response(params, manager)
    result = []
    sap_orders_from_api = api_response.get("data", [])
    data_items_from_api = api_response.get("dataItem", [])
    remove_parent_item_no_for_child_search(data_items_from_api)

    if not sap_orders_from_api or not data_items_from_api:
        return result
    add_is_not_ref_to_es_25_res(sap_orders_from_api, data_items_from_api)
    if input_data.get("is_order_tracking", False):
        ots_response = prepare_payload_and_call_ots(input_data, info)
        extract_and_map_ots_response_to_sap_response(data_items_from_api, ots_response)
    else:
        set_default_quantity_to_es25_response(data_items_from_api)
    mapping_sold_to_with_sold_to_name = {}
    mapping_sold_to_with_order = {}
    mapping_order_with_order_lines = {}
    mapping_order_with_order_no = {}
    total_sold_to = 0
    sold_grouping_dic_key_sold_to = {}
    sold_to_list = [order.get('soldTo') for order in sap_orders_from_api]
    filtered_otc_sold_to_list = SoldToMasterRepo.filter_otc_sold_to_from_sold_to_list(set(sold_to_list),
                                                                                      OTC_ACCOUNT_GROUPS)

    for order in sap_orders_from_api:
        sold_to = order.get('soldTo')
        sales_document_number = order.get('sdDoc')
        sold_to_name = order.get('soldToName1')
        if sold_to in filtered_otc_sold_to_list:
            sold_grouping_dic_key = f'{sold_to}-{sold_to_name}'
        else:
            sold_grouping_dic_key = sold_to
        if sold_grouping_dic_key not in mapping_sold_to_with_order:
            total_sold_to += 1

            mapping_sold_to_with_sold_to_name[sold_grouping_dic_key] = sold_to_name
            mapping_sold_to_with_order[sold_grouping_dic_key] = []
            sold_grouping_dic_key_sold_to[sold_grouping_dic_key] = sold_to

        mapping_sold_to_with_order[sold_grouping_dic_key].append(sales_document_number)
        mapping_order_with_order_lines[sales_document_number] = [order_line for order_line in data_items_from_api if
                                                                 order_line.get("sdDoc") == sales_document_number]
        mapping_order_with_order_no[sales_document_number] = order

    for sold_to_code, list_order_no_of_sold_to in mapping_sold_to_with_order.items():
        list_order_line_of_sold_to = []
        for order_no in list_order_no_of_sold_to:
            current_order_lines = mapping_order_with_order_lines[order_no]
            derive_parent_price_and_weight_for_bom(current_order_lines)
            list_order_line_of_sold_to.extend(
                get_order_line_by_delivery_block(current_order_lines, delivery_block_input)
            )

        if check_sales_order_need_to_filter_in_database(input_data):
            list_order_line_of_sold_to = filter_sales_order_in_database(list_order_line_of_sold_to,
                                                                        mapping_order_with_order_lines, input_data)
        if not list_order_line_of_sold_to:
            total_sold_to -= 1
            continue
        order_lines = make_list_order_line_for_sap_order_line(
            list_order_line_of_sold_to,
            mapping_order_with_order_no,
        )
        row = {
            "total_sold_to": total_sold_to,
            "sold_to": sold_grouping_dic_key_sold_to.get(sold_to_code, sold_to_code),
            "sold_to_name_1": mapping_sold_to_with_sold_to_name.get(sold_to_code),
            "order_lines": order_lines,
            "summary": make_summary_for_sold_to_from_order_line_in_es25(list_order_line_of_sold_to)
        }
        result.append(row)
    return result


def resolve_list_of_sale_order_sap_order_pending(input_data, info):
    params = prepare_param_for_es25_order_pending(input_data)
    sort_columns = input_data.get('sold_to_sort')
    api_response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
        SapEnpoint.ES_25.value,
        params
    )
    # api_response = ES25_SAMPLE_RESPONSE1
    res = []
    sap_orders = api_response.get("data", [])
    if not sap_orders:
        return []
    data_item = api_response.get("dataItem", [])
    remove_parent_item_no_for_child_search(data_item)
    if input_data.get("is_order_tracking", False):
        ots_response = prepare_payload_and_call_ots(input_data, info)
        extract_and_map_ots_response_to_sap_response(data_item, ots_response)
    else:
        set_default_quantity_to_es25_response(data_item)
    if not sap_orders or not data_item:
        return res
    if input_data.get("product_groups") == "All":
        product_groups = resolve_material_group_from_db()
    else:
        product_groups = input_data.get("product_groups", "")
    data_item = list(map(format_item_no, data_item))
    data_item = mapping_material_group1(data_item, product_groups)
    list_sold_to = set(list(map(lambda x: x.get("soldTo"), sap_orders)))
    otc_sold_tos = (SoldToMasterRepo.filter_otc_sold_to_from_sold_to_list
                    (list_sold_to, OTC_ACCOUNT_GROUPS))
    # group items by sold_to code
    for sold_to in sorted(list_sold_to):
        orders = list(filter(lambda x: x.get("soldTo") == sold_to, sap_orders))
        if sold_to in otc_sold_tos:
            # group otc orders by sold_to_name
            otc_order_groups = group_otc_orders(orders)
            for sold_to_name, otc_orders in otc_order_groups.items():
                res.append(group_items_by_sold_to(otc_orders, data_item, sort_columns))
        else:
            res.append(group_items_by_sold_to(orders, data_item, sort_columns))
    return res


def resolve_material_group_from_db():
    return (sap_master_data_models.MaterialSaleMaster.objects.exclude(material_group1__isnull=True).
            values_list('material_group1', flat=True).distinct())


def resolve_list_of_sale_order_and_excel(input_data, info):
    list_of_sale_order_sap = resolve_list_of_sale_order_sap(input_data, info)
    if not list_of_sale_order_sap:
        return {}
    # list_of_sale_order_sap_to_excel = make_excel_from_list_of_sale_order_sap(list_of_sale_order_sap)
    return {
        'excel': None,
        'list_of_sale_order_sap': list_of_sale_order_sap,
    }


def get_address_name_from_partner_address(address):
    address_attrs = [
        address.street,
        address.street_sup1,
        address.street_sup2,
        address.street_sup3,
        address.district,
        address.city,
        address.postal_code,
    ]
    address_attrs = [attr if attr else "" for attr in address_attrs]
    address_text = " ".join(address_attrs)

    name_attrs = [
        address.name1,
        address.name2,
        address.name3,
        address.name4,
    ]

    name_attrs = [attr if attr else "" for attr in name_attrs]
    name = " ".join(name_attrs)

    return {"address": address_text, "name": name}


def get_order_line_by_delivery_block(order_lines, delivery_block_input):
    list_order_line_of_sold_to = []
    for order_line in order_lines:
        if not delivery_block_input or (
                delivery_block_input == 'BLOCK' and order_line.get('deliveryBlock') == '09') or (
                delivery_block_input == 'UNBLOCK' and not order_line.get('deliveryBlock')) or (
                delivery_block_input == 'All'):
            list_order_line_of_sold_to.append(order_line)
    return list_order_line_of_sold_to


def resolve_download_list_of_sale_order_excel(input_data, info):
    list_of_sale_order_sap = resolve_list_of_sale_order_sap(input_data, info)
    if not list_of_sale_order_sap:
        return {}
    sort_data_in_desc_or_asc(input_data, list_of_sale_order_sap)
    is_order_tracking = input_data.get('is_order_tracking', False)
    list_of_sale_order_sap_to_excel = make_excel_from_list_of_sale_order_sap(list_of_sale_order_sap, is_order_tracking)
    return {
        'excel': list_of_sale_order_sap_to_excel
    }


def sort_data_in_desc_or_asc(input_data, list_of_sale_order_sap):
    if input_data.get('sort_by_field'):
        sort_field = input_data.get('sort_by_field', {}).get("sort_field")
        reverse = input_data.get('sort_by_field', {}).get("sort_type") == 'DESC'
        if sort_field:
            for order in list_of_sale_order_sap:
                bom_child_list, parent_and_normal_order_line_list = separate_parent_and_bom_order_lines(
                    order['order_lines'])

                sorted_parent_and_normal_order_line_list = sort_list(parent_and_normal_order_line_list,
                                                                     reverse, sort_by_field=sort_field)
                sorted_bom_child_list = sort_list(bom_child_list, reverse, sort_by_field=sort_field)

                order['order_lines'] = sorted_and_merged_order_line_list(reverse, sorted_bom_child_list,
                                                                         sorted_parent_and_normal_order_line_list)


def sort_list(order_line_list, reverse, **kwargs):
    sorted_list = []
    # if order_no(then system will sort by Item No. ascending as secondary sorting fields automatically)
    sort_field = kwargs.get('sort_by_field')
    if "order_no" == sort_field:
        if reverse:
            sorted_list = sorted(order_line_list,
                                 key=lambda x: (-int(x[sort_field]), int(x['item_no'])))
        else:
            sorted_list = sorted(order_line_list,
                                 key=lambda x: (int(x[sort_field]), int(x['item_no'])))

    '''if Create_Date then system will sort by order_no. and Item No. ascending as secondary-third sorting
       fields automatically. if po_no then system will sort by order_no. and Item No. ascending as
       secondary-third sorting fields automatically. if original_request_date: then system will sort by order_no
       and Item No. ascending as secondary-third sorting fields automatically'''

    if sort_field == "po_no" or sort_field == "create_date" or sort_field == "req_delivery_date":
        if reverse:
            sorted_list = sorted(order_line_list,
                                 key=lambda x: (
                                     str(x[sort_field]).lower() if sort_field == "po_no" else datetime.strptime(
                                         x[sort_field], '%d/%m/%Y'), -int(x['order_no']),
                                     -int(x['item_no'])),
                                 reverse=True)
        else:
            sorted_list = sorted(order_line_list, key=lambda x: (
                str(x[sort_field]).lower() if sort_field == "po_no" else datetime.strptime(x[sort_field], '%d/%m/%Y'),
                int(x['order_no']), int(x['item_no'])))

    return sorted_list
