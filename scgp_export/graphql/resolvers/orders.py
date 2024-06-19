import uuid
from django.core.exceptions import ValidationError
from django.db.models import IntegerField
from django.db.models.functions import Cast

from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from sap_master_data.models import SoldToChannelMaster
from sap_migration import models as sap_migration_models
from sap_master_data import models as sap_master_data_models
from scgp_export.graphql.enums import ScgpExportOrderStatus, SapEnpoint
from scg_checkout.graphql.resolves.orders import call_sap_es26
from scgp_export.graphql.helper import sync_export_order_from_es26
from scg_checkout.graphql.resolves.contracts import sync_contract_material


def resolve_export_order(order_id):
    return sap_migration_models.Order.objects.filter(id=order_id).first()


def resolve_export_order_by_so_no(info, so_no):
    response = call_sap_es26(so_no=so_no, sap_fn=info.context.plugins.call_api_sap_client)
    info.variable_values.update({"sap_order_response": response})
    order = sync_export_order_from_es26(response)
    info.variable_values.update({"order": order})
    return response


def resolve_order_lines(order_id, **kwargs):
    sort_by = kwargs.get("sort_by")
    if sort_by is None:
        # Default sort by material_code asc
        return sap_migration_models.OrderLines.objects.filter(order_id=order_id).annotate(
            fkn_int_cast=Cast('item_no', output_field=IntegerField()),
        ).order_by('fkn_int_cast', 'material_code', 'pk')

    return sap_migration_models.OrderLines.objects.filter(order_id=order_id).order_by(
        *["{}{}".format(sort_by["direction"], field) for field in sort_by["field"]]
    )


def resolve_export_orders():
    return sap_migration_models.Order.objects.all()


def resolve_filter_ship_to_export_order(input_string):
    return sap_migration_models.Order.objects.filter(ship_to__icontains=input_string).values("ship_to")


def resolve_export_order_companies_by_user():
    return sap_master_data_models.SalesOrganizationMaster.objects.all()


def resolve_export_order_business():
    return sap_migration_models.BusinessUnits.objects.all().order_by("name", "id")


def resolve_export_order_companies_by_bu():
    return sap_master_data_models.SalesOrganizationMaster.objects.all()


def resolve_export_list_orders():
    return sap_migration_models.Order.objects.filter(distribution_channel__code__in=['30']).all()


def resolve_export_list_draft():
    return sap_migration_models.Order.objects.filter(status="draft").all()


def resolve_scgp_order_status():
    status = [(key, val.value) for key, val in vars(ScgpExportOrderStatus).items() if not key.startswith("_")]
    return status


def resolve_get_credit_limit(info, data_input):
    sold_to_code = data_input.get("sold_to_code", "").split("-")[0].strip()
    sales_org_code = data_input.get("sales_org_code", "")
    contract_no = data_input.get("contract_no")
    if sales_org_code:
        sales_org_code = sales_org_code.split("-")[0].strip()
    if contract_no and (not sold_to_code or not sales_org_code):
        contract = sap_migration_models.Contract.objects.filter(code=contract_no).first()
        if not sold_to_code:
            sold_to_code = contract and contract.sold_to_code or None
        if not sales_org_code:
            sales_org_code = contract and contract.sales_organization and contract.sales_organization.code or None
    credit_area_object = SoldToChannelMaster.objects.filter(sold_to_code=sold_to_code).first()
    credit_control_area = None
    if credit_area_object:
        credit_control_area = credit_area_object.credit_area
    if not credit_control_area and not sales_org_code:
        raise ValueError("Credit control area cannot be determined to send to SAP. Data issue in database")
    params = {
        "piMessageId": str(uuid.uuid1().int),
        "customerId": sold_to_code,
        "creditControlArea": credit_control_area or sales_org_code,
    }
    sap_response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_get(
        SapEnpoint.ES_10.value,
        params
    )
    data = sap_response.get("data", None)
    if not data:
        raise ValidationError("API Server Seem Not Working!")
    credit_limit = {
        "credit_control_area": data[0].get("creditControlArea", sales_org_code),
        "currency": data[0].get("currency", "THB"),
        "credit_limit": data[0].get("creditLimit", 0),
        "credit_account": data[0].get("creditAccount", contract_no),
        "credit_exposure": data[0].get("creditExposure", 0),
        "credit_limit_used": data[0].get("creditLimitUsed", 0),
        "credit_avaiable": float(data[0].get("creditLimit", 0)) - float(data[0].get("creditExposure", 0)),
        "receivables": data[0].get("receivables", 0),
        "special_liabil": data[0].get("specialLiabil", 0),
        "sale_value": data[0].get("saleValue", 0),
        "second_receivables": data[0].get("secondReceivables", 0),
        "credit_block_status": data[0].get("creditBlockStatus", False),
    }

    return credit_limit


def resolve_currency(currency_id):
    try:
        return sap_migration_models.CurrencyMaster.objects.filter(id=currency_id).first().code
    except Exception:
        return None
