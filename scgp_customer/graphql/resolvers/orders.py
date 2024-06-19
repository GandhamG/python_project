import json
from datetime import date, timedelta

from django.db.models import Sum, F, Q, Value, TextField
from django.db.models.functions import Concat

from saleor.plugins.scg_sap_client_api.example_response import ES_25
from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from sap_migration import models as sap_migration_models
from sap_master_data import models as sap_master_data_models
from scg_checkout.graphql.helper import PAYMENT_TERM_MAPPING
from scgp_customer.graphql.helpers import prepare_es25_params
from scgp_export.graphql.enums import SapEnpoint


def resolve_customer_order(order_id):
    return sap_migration_models.Order.objects.filter(id=order_id, type="customer").first()


def resolve_order_lines(order_id):
    return sap_migration_models.OrderLines.objects.filter(order_id=order_id).order_by("item_no")


def resolve_representatives(sold_to_id):
    return sap_migration_models.SoldTo.objects.get(id=sold_to_id).representatives.all()


def resolve_available_quantity(order_id, contract_product_id):
    return sap_migration_models.OrderLines.objects.filter(order_id=order_id,
                                                          contract_material_id=contract_product_id).values(
        "contract_material").order_by("contract_material").annotate(sum_quantity=Sum("quantity")).annotate(
        available_quantity=F("contract_material__remaining_quantity") - F("sum_quantity")).first().get(
        "available_quantity", 0)


def resolve_fail_order_lines(order_id):
    order_lines = sap_migration_models.OrderLines.objects.filter(order_id=order_id).order_by('item_no').all()
    result = []
    for order_line in order_lines:
        if not order_line.confirmed_date:
            iplan_confirmed_date = date.today() + timedelta(days=10)
        else:
            iplan_confirmed_date = order_line.confirmed_date

        if iplan_confirmed_date != order_line.request_date:
            result.append(order_line)

    return result


def resolve_material_variant_code(material_variant_id):
    try:
        return sap_migration_models.MaterialVariantMaster.objects.filter(id=material_variant_id).first().code
    except Exception:
        return None


def resolve_material_description(material_variant_id):
    try:
        return sap_migration_models.MaterialVariantMaster.objects.filter(id=material_variant_id).first().description_en
    except Exception:
        return None


def resolve_confirmed_date(order_line_id):
    order_line = sap_migration_models.OrderLines.objects.filter(id=order_line_id).first()
    if order_line and order_line.confirmed_date is not None:
        return order_line.confirmed_date
    else:
        return date.today() + timedelta(days=10)


def resolve_order_quantity_ton(root, info):
    try:
        quantity = root.quantity
        material_code = root.material_variant.code
        conversion = sap_master_data_models.Conversion2Master.objects.filter(
            material_code=material_code,
            to_unit="ROL"
        ).last()
        calculation = conversion.calculation
        order_quantity_ton = float(quantity) * float(calculation) / 1000
        return order_quantity_ton
    except Exception:
        return root.quantity


def resolve_filter_customer_business_unit():
    return list(sap_migration_models.BusinessUnits.objects.all().order_by("name", "id").values("id", "name", "code"))


def resolve_filter_customer_company_by_bu():
    return sap_master_data_models.SalesOrganizationMaster.objects.all()


def resolve_filter_customer_sales_group():
    return sap_migration_models.SalesGroupMaster.objects.all()


def resolve_filter_material_code_name_customer_order(qs):
    return sap_migration_models.MaterialVariantMaster.objects.filter(code__in=qs).exclude(material__delete_flag="X")


def resolve_customer_orders(created_by):
    return sap_migration_models.Order.objects \
        .exclude(status__in=["draft", "confirmed"]) \
        .filter(type="customer", created_by=created_by).all()


def resolve_currency(currency_id):
    try:
        return sap_migration_models.CurrencyMaster.objects.filter(id=currency_id).first().code
    except Exception:
        return None


def resolve_sales_unit_order(root, info):
    try:
        sales_unit = root.material_variant.sales_unit
        return sales_unit
    except Exception:
        return None


def resolve_customer_sold_to_order(contract):
    try:
        sold_to = sap_migration_models.Contract.objects.filter(id=contract).first().sold_to
        return f"{sold_to.sold_to_code} - {sold_to.sold_to_name}"
    except Exception:
        return None


def resolve_material_variant(root, info):
    return root.material_variant


def resolve_customer_order_confirmation():
    return sap_migration_models.Order.objects.filter(
        Q(distribution_channel_id=1)
        | Q(distribution_channel_id=2),
        type='customer').all()


def resolve_filter_customer_order_confirmation_company():
    return sap_master_data_models.CompanyMaster.objects.all()


def resolve_non_confirm_quantity(root):
    try:
        if root.quantity > root.assigned_quantity:
            rs = root.quantity - root.assigned_quantity
            return rs
    except:
        return None


def resolve_customer_orders_from_sap(info, data_input):
    res = []
    if not data_input:
        return res

    params = prepare_es25_params(data_input)
    api_response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
        SapEnpoint.ES_25.value,
        params
    )
    sap_orders = api_response.get("data", [])
    sap_orders_to_dict = {order.get("sdDoc", ""): order for order in sap_orders}
    sap_order_data_items = api_response.get("dataItem", [])
    for data_item in sap_order_data_items:
        sd_doc = data_item["sdDoc"]
        sap_order = sap_orders_to_dict.get(sd_doc, None)
        if sap_order:
            sap_orders_to_dict[sd_doc] = {
                **sap_orders_to_dict[sd_doc],
                **data_item
            }

    e_ordering_order_dicts = sap_migration_models.Order.objects \
        .filter(so_no__in=sap_orders_to_dict.keys()) \
        .distinct('so_no') \
        .in_bulk(field_name='so_no')

    company_mapping = sap_master_data_models.CompanyMaster.objects \
        .annotate(code_name=Concat('code', Value(' - '), 'short_name', output_field=TextField())) \
        .in_bulk(field_name='code')

    for order_no, order in sap_orders_to_dict.items():
        order_in_db = e_ordering_order_dicts.get(order_no, None)
        order_id = order_in_db.id if order_in_db else None
        status = order_in_db.status if order_in_db else ""

        res.append({
            "id": order_id,
            "sd_doc": order.get("sdDoc", ""),
            "status": order.get("status", ""),
            "create_date": order.get("createDate", ""),
            "create_time": order.get("createTime", ""),
            "po_no": order.get("poNo", ""),
            "sales_org": getattr(company_mapping.get(str(order.get("salesOrg", ""))), "code_name", ""),
            "description_in_contract": order.get("descriptionInContract", ""),
            "credit_status": order.get("creditStatus", ""),
            "deliver_status": order.get("deliveryStatus", ""),
            "sold_to": order.get("soldTo", ""),
            "sold_to_name_1": order.get("soldToName1", ""),
            "ship_to": order.get("shipTo", ""),
            "ship_to_name_1": order.get("shipToName1", ""),
            "country_sh": order.get("countrySh", ""),
            "country_name": order.get("countryName", ""),
            "incoterm_s1": order.get("incoterms1", ""),
            "incoterm_s2": order.get("incoterms2", ""),
            "payment_term": order.get("paymentTerm", ""),
            "payment_term_desc": PAYMENT_TERM_MAPPING.get(order.get("paymentTerm", ""), ""),
            "e_ordering_status": status,
            "contract_pi": order.get("contractPI", ""),
        })
    return res


def resolve_description_en_preview_order(variant_code):
    try:
        material = sap_master_data_models.MaterialMaster.objects.filter(material_code=variant_code).first()
        return material.description_en
    except:
        return None


def resolve_weight_per_unit(root):
    # get the latest conversion
    conversion = sap_master_data_models.Conversion2Master.objects.filter(
        material_code=root.material_variant.code, to_unit="ROL").last()
    if not conversion:
        return round(root.weight, 3)
    return round(float(conversion.calculation) / 1000, 3)


def resolve_total_weight(root):
    return round(resolve_weight_per_unit(root) * root.quantity, 3)
