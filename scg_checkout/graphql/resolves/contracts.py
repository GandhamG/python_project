import json
from typing import Union
import random
import uuid
from datetime import datetime, timedelta
from functools import reduce

from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Q, Subquery, OuterRef

import sap_migration.models
import sap_master_data.models as master_model
from common.helpers import update_instance_fields
from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from saleor.plugins.manager import get_plugins_manager
from sap_master_data import models as master_models
from sap_master_data.models import SalesOrganizationMaster, CompanyMaster
from sap_migration import models as migration_models
from sap_migration.models import ContractMaterial
from scg_checkout.graphql.enums import MaterialType
from scg_checkout.graphql.helper import get_name1_from_partner_code, make_order_header_text_mapping, \
    is_default_sale_unit_from_contract, extract_item_text_data_sap_es14, update_active_for_missing_contract_materials
from scg_checkout.sap_contract_list import sap_contract_mapping
from scgp_export.graphql.enums import SapEnpoint, MaterialGroup
from scgp_export.graphql.resolvers.export_sold_tos import resolve_display_text
from scgp_require_attention_items.graphql.helper import get_sales_orgs_by_codes, get_distribution_channels_by_codes

mapping_code_for_contract_materials = {
    "Z004": "remark"
}


def resolve_contracts(info, **kwargs):
    sold_to_code = kwargs.get("sold_to_code")
    contract_no = kwargs.get("contract_no")
    contract_code_sap = kwargs.get("filter", {}).get("sap_code", None)
    queryset = migration_models.Contract.objects.all()
    queryset = queryset.filter(sold_to__sold_to_code=sold_to_code, distribution_channel__code__in=['10', '20'])
    if contract_code_sap is not None:
        queryset = migration_models.Contract.objects.filter(code__in=contract_code_sap)
    if contract_no:
        queryset = queryset.filter(code=contract_no)
    return queryset


def resolve_contract(info, id):
    return migration_models.Contract.objects.filter(id=id).first()


def resolve_products(id, sort_by, info):
    queryset = ContractMaterial.objects.filter(contract_id=id)
    list_sap_contract_item = info.variable_values.get("list_contract_item", None)

    if list_sap_contract_item is not None:
        queryset = ContractMaterial.objects.filter(id__in=list_sap_contract_item)

    if sort_by is not None:
        queryset = queryset.order_by(
            *["{}{}".format(sort_by["direction"], field) for field in sort_by["field"]]
        )

    return queryset.order_by("item_no")


def resolve_contract_product(info, contract_material_id):
    contract_material = migration_models.ContractMaterial.objects.filter(
        id=contract_material_id
    ).first()
    return contract_material


def call_sap_api(info, api, method, params):
    instance = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value)
    req = instance.request_mulesoft_get
    if method == SapEnpoint.METHOD_POST.value:
        req = instance.request_mulesoft_post
    response = req(api, params)
    return response.get("data", [])


def call_sap_api_get_contracts_export_pis(contract_code, context: Union[dict, None] = None):
    manager = get_plugins_manager()
    sap_fn = manager.call_api_sap_client
    contract_code = contract_code.zfill(10)

    response = get_sap_contract_items(sap_fn, contract_no=contract_code, context=context)

    response_data = response.get("data", [])
    if len(response_data) == 0:
        return None, {}

    response_data = response_data[0]
    contact_person_list = response_data.get("contactPerson", [])
    contact_persons = ", ".join(
        [f"{contact_person.get('contactPersonNo')} - {contact_person.get('contactPersonName')}"
         for contact_person in contact_person_list]
        if "" not in contact_person_list
        else ""
    )
    mapped_sale_orgs = SalesOrganizationMaster.objects.all().in_bulk(field_name='code')
    sale_org = mapped_sale_orgs.get(response_data.get("saleOrg"))
    mapped_companies = CompanyMaster.objects.all().in_bulk(field_name='code')
    sold_to = sap_migration.models.SoldToMaster.objects.all().in_bulk(field_name='sold_to_code')
    mock_start_date = datetime.strftime(datetime.now().date(), "%d/%m/%Y")
    mock_end_date = datetime.strftime(
        datetime.now().date() + timedelta(days=30), "%d/%m/%Y"
    )
    contract_sale_detail = {
        "sold_to": sold_to.get(response_data.get("soldTo")),
        "code": response_data.get("contractNo", contract_code),
        "company": mapped_companies.get(str(response_data.get("companyCode", "0750")), None),
        "sales_organization": sale_org,
        "business_unit": sale_org.business_unit if sale_org else None,
        "payment_term": response_data.get("pymTermDes", ""),
        "po_no": response_data.get("poNo", ""),
        "incoterm": response_data.get("incoterms1"),
        "ship_to": f'{response_data.get("shipTo", "")} - {response_data.get("shipToName", "")}',
        "ship_to_name": response_data.get("shipToName", ""),
        "ship_to_country": response_data.get("country", ""),
        "po_date": datetime.now().date(),
        "sold_to_code": response_data.get("customerNo", ""),
        "payment_term_key": response_data.get("pymTermKey", ""),
        "contact_person": contact_persons,
        "start_date": datetime.strptime(response_data.get("validFrom", mock_start_date), "%d/%m/%Y").date(),
        "end_date": datetime.strptime(response_data.get("validTo", mock_end_date), "%d/%m/%Y").date(),
        "project_name": response_data.get("projectName", ""),
    }
    order_text_list = response_data.get("orderText", [])
    order_text_list_data = get_data_from_order_text_list(order_text_list)
    order_header_text_list = make_order_header_text_mapping(order_text_list)
    contract_sale_detail = {**contract_sale_detail, **order_text_list_data, **order_header_text_list}
    now = datetime.now().strftime("%d%m%Y")
    contract_sale_detail.update({
        "etd": datetime.strptime(order_text_list_data.get("etd") or now, "%d%m%Y"),
        "eta": datetime.strptime(order_text_list_data.get("etd") or now, "%d%m%Y"),
    })

    contract, _ = migration_models.Contract.objects.update_or_create(
        code=contract_code, defaults=contract_sale_detail
    )
    return contract, response


def call_sap_api_get_contracts(info, **kwargs):
    sold_to = ""
    contract_code = kwargs.get("filter").get("code")
    if contract_code:
        contract, _ = call_sap_api_get_contracts_export_pis(contract_code.zfill(10))
        kwargs.get("filter").update({
            "sap_code": (contract.code,) if contract else []
        })
        return kwargs

    customer_no = None
    if kwargs.get("sold_to_code", ""):
        customer_no = kwargs.get("sold_to_code", "").zfill(10)

    doc_type = "ZCQ"
    if customer_no is None:
        customer_no = kwargs.get("filter").get("sold_to").zfill(10)
        doc_type = "ZPI"
        if customer_no:
            customer_no = customer_no.split("-")[0].strip()

    params = {
        "piMessageId": str(uuid.uuid1().int),
        "customerNo": customer_no or "",
        "validFrom": datetime.now().strftime("%d/%m/%Y"),
        "validTo": datetime.now().strftime("%d/%m/%Y"),
        "saleOrgList": [
            {
                "saleOrg": "0750"
            },
            {
                "saleOrg": "7540"
            },
        ],
        "docType": doc_type,
        "matCode": ""
    }
    rs = call_sap_api(info, SapEnpoint.ES_13.value, SapEnpoint.METHOD_POST.value, params)
    sap_contract_mapping(rs, sold_to)
    list_contract_code = [contract.get("contractNo") for contract in rs]
    kwargs.get("filter").update({
        "sap_code": list_contract_code
    })

    return kwargs


def resolve_routes():
    return migration_models.Route.objects.all()


def get_order_text_list_when_duplicate_item_no_text_id(order_text_list):
    tmp = dict()
    for order_text in order_text_list:
        code = f'{order_text["itemNo"]}_{order_text["textId"]}'
        if code in tmp:
            if order_text["lang"] == 'EN':
                tmp[code] = order_text
        else:
            tmp[code] = order_text
    return list(tmp.values())


def sync_lang_from_order_text_list_or_db(order_text_list, contract):
    order_text_list = get_order_text_list_when_duplicate_item_no_text_id(order_text_list)
    for order_text in order_text_list:
        if "lang" in order_text and order_text.get("lang") and order_text.get("lang") != " ":
            language = order_text.get("lang")
        else:
            sold_to_code = contract.sold_to.sold_to_code
            sales_organization_code = contract.sales_organization.code
            distribution_channel_code = contract.distribution_channel.code
            division_code = contract.division.code
            sold_to_text_master = master_models.SoldToTextMaster.objects.filter(
                sold_to_code=sold_to_code,
                sales_organization_code=sales_organization_code,
                distribution_channel_code=distribution_channel_code,
                division_code=division_code,
                text_id=order_text.get("textId")
            ).first()
            language = sold_to_text_master and sold_to_text_master.language or None

        defaults = {
            'contract': contract,
            'text_id': order_text.get("textId"),
            'item_no': order_text.get("itemNo"),
            'language': language
        }

        _obj, _created = migration_models.OrderTextLang.objects.update_or_create(
            contract=contract,
            text_id=order_text.get("textId"),
            item_no=order_text.get("itemNo"),
            defaults=defaults
        )


def get_data_from_order_text_list(order_text_list):
    result = {}
    mapping = {
        "Z014": "port_of_loading",
        "Z004": "shipping_mark",
        "Z019": "uom",
        "Z013": "port_of_discharge",
        "Z022": "no_of_containers",
        "ZK35": "gw_uom",
        "Z012": "payment_instruction",
        "Z016": "remark",
        "ZK08": "production_information",
        "Z001": "internal_comments_to_warehouse",
        "Z038": "etd",
        "Z066": "eta",
        "Z008": "surname",
        "Z067": "external_comments_to_customer",
        "Z002": "internal_comments_to_logistic",
        "ZK01": "web_user_line"
    }

    result = {}
    for key, value in mapping.items():
        order_text_data = sorted(
            list(filter(
                lambda order_text: order_text["textId"] == key and order_text.get("itemNo") == "000000", order_text_list
            )), key=lambda d: d.get("lang", "")
        )
        order_text_obj = next(iter(order_text_data), {})
        order_texts = order_text_obj.get("headerTextList", [])
        result[value] = "\n".join((x.get("headerText") for x in order_texts)) or None
        if lang := order_text_obj.get("lang"):
            result[value + "_lang"] = lang

    return result


def sync_contract_material(contract_id=None, contract_no=None, es26_response=None, is_create=False,
                           context: Union[dict, None] = None):
    try:
        contract = (
            migration_models.Contract.objects
            .filter(Q(id=contract_id) | Q(code=contract_no, code__isnull=False))
            .first()
        )
        contract_no = contract_no or contract.code
    except migration_models.Contract.DoesNotExist and not is_create:
        pass
    contract, response = call_sap_api_get_contracts_export_pis(contract_no, context=context)
    currency = ""

    try:
        response_data = response.get("data", [])
        if len(response_data) == 0:
            return list()

        response_data = response_data[0]

        # Save payment term code for contract
        update_instance_fields(
            contract,
            {
                "payment_term_key": response_data.get("pymTermKey"),
                "payment_term": response_data.get("pymTermDes")
            },
            save=True
        )

        condition_list = response_data.get("conditionList")
        for item in condition_list:
            if item.get('currency'):
                currency = item.get('currency')
                break
        list_items = response_data.get("contractItem", [])
        list_items_mat_group = ",".join(set(filter(None, [item.get("matGroup1", None) for item in list_items])))
        if es26_response:
            es26_response["contractItem"] = list_items
        contact_person_list = response_data.get("contactPerson", [])
        contact_persons = ", ".join(
            [f"{contact_person.get('contactPersonNo')} - {contact_person.get('contactPersonName')}"
             for contact_person in contact_person_list]
            if "" not in contact_person_list
            else ""
        )

        order_text_list = response_data.get("orderText", [])
        order_text_list_data = get_data_from_order_text_list(order_text_list)
        order_header_text_data = make_order_header_text_mapping(order_text_list)
        sync_lang_from_order_text_list_or_db(order_text_list, contract)
        contract_sale_detail = {
            "distribution_channel": response_data.get("distributionChannel", ""),
            "division": response_data.get("division", ""),
            "sale_office": response_data.get("saleOffice", ""),
            "sale_group": response_data.get("saleGroup", ""),
            "bill_to": response_data.get("billTo", ""),
            "customer_no": response_data.get("customerNo", ""),
            "ship_to": response_data.get("shipTo") + " - " + response_data.get("shipToName"),
            "ship_to_name": response_data.get("shipToName"),
            "unloading_point": response_data.get("unloadingPoint"),
            "payer": response_data.get("payer"),
            "contact_person": contact_persons,
            "sales_employee": response_data.get("salesEmployee"),
            "author": response_data.get("author"),
            "end_customer": response_data.get("endCustomer"),
            "po_no": response_data.get("poNo"),
            "currency": currency,
            "incoterms_1": response_data.get("incoterms1"),
            "incoterms_2": response_data.get("incoterms2"),
            "usage": response_data.get("usage", None),
            "usage_no": response_data.get("usageNo", None),
            "prc_group1": list_items_mat_group,
        }
        contract_sale_detail = {**contract_sale_detail, **order_text_list_data, **order_header_text_data}
        sync_contract_sale_detail(contract, contract_sale_detail)
        list_condition = response_data.get("conditionList", [])
        contract_item_objects = reduce(
            lambda previous, current: {**previous, current.get('itemNo'): current},
            list_items,
            {}
        )

        extracted_condition_type = ['ZN00', 'ZPR2']
        for item_no in contract_item_objects.keys():
            item_conditions = list(
                filter(
                    lambda item:
                    item.get('conditionType') in extracted_condition_type
                    and item.get('itemNo') == item_no,
                    list_condition
                )
            )
            commission_zcm1 = list(
                filter(
                    lambda item:
                    item.get('conditionType') == "ZCM1"
                    and item.get('itemNo') == item_no,
                    list_condition
                )
            )
            commission_zcm3 = list(
                filter(
                    lambda item:
                    item.get('conditionType') == "ZCM3"
                    and item.get('itemNo') == item_no,
                    list_condition
                )
            )
            contract_item_objects.get(item_no)['conditions'] = item_conditions
            contract_item_objects.get(item_no)['commission_zcm1'] = commission_zcm1
            contract_item_objects.get(item_no)['commission_zcm3'] = commission_zcm3

        return map_sap_contract_item(contract, contract_item_objects, order_text_list)
    except AttributeError as e:
        # Consider in the future use logger to catch exception
        return list()


def get_bill_to_obj(bill_to):
    if not bill_to:
        return None

    partner = master_models.SoldToChannelPartnerMaster.objects.filter(partner_code=bill_to).first()
    if partner is None:
        return None

    bill_to_obj = master_models.SoldToPartnerAddressMaster.objects.filter(partner_code=partner.partner_code).first()
    return bill_to_obj


def sync_contract_sale_detail(contract: migration_models.Contract, params: dict):
    distribution_channel = migration_models.DistributionChannelMaster.objects.filter(
        code=params.get("distribution_channel")).first()
    division = migration_models.DivisionMaster.objects.filter(code=params.get("division")).first()
    sale_group = migration_models.SalesGroupMaster.objects.filter(code=params.get("sale_group")).first()
    sale_office = migration_models.SalesOfficeMaster.objects.filter(code=params.get("sale_office")).first()

    "In case we don't have any unloading point from ES-14, get the first row from database, probably..."
    if params.get("unloading_point") is None:
        unloading_point_obj = master_models.SoldToUnloadingPointMaster.objects.filter(
            sold_to_code=params.get("customer_no")).first()
        unloading_point = unloading_point_obj.unloading_point if unloading_point_obj is not None else None
    else:
        unloading_point = params.get("unloading_point")

    bill_to_obj = get_bill_to_obj(params.get("bill_to"))
    bill_to_format = ""
    if params.get('bill_to'):
        bill_to_format = f"{params.get('bill_to')} - {bill_to_obj.name1}" if bill_to_obj \
            else f"{params.get('bill_to')} - "

    contract.distribution_channel = distribution_channel
    contract.division = division
    contract.sales_group = sale_group
    contract.sales_office = sale_office
    contract.bill_to = bill_to_format
    contract.po_no = params.get('po_no', "")
    contract.payer = f"{params.get('payer', '')} - {resolve_display_text(params.get('payer', ''))}"
    contract.contact_person = get_name1_from_partner_code(params.get('contact_person', ""))
    contract.sales_employee = f"{params.get('sales_employee', '')} - {resolve_display_text(params.get('sales_employee', ''))}"
    contract.author = f"{params.get('author', '')} - {resolve_display_text(params.get('author', ''))}"
    contract.shipping_mark = params.get('shipping_mark', "")
    contract.end_customer = get_name1_from_partner_code(params.get('end_customer', ""))
    contract.currency = params.get('currency', "")
    contract.port_of_loading = params.get('port_of_loading', "")
    contract.uom = params.get('uom', "")
    contract.port_of_discharge = params.get('port_of_discharge', "")
    contract.no_of_containers = params.get('no_of_containers', "")
    contract.gw_uom = params.get('gw_uom', "")
    contract.payment_instruction = params.get('payment_instruction', "")
    contract.production_information = params.get('production_information', "")
    contract.internal_comments_to_warehouse = params.get('internal_comments_to_warehouse', "")
    contract.remark = params.get('remark')
    contract.incoterms_2 = params.get('incoterms_2')
    contract.etd = datetime.strptime(params.get('etd'), '%d%m%Y') if params.get('etd') else None
    contract.eta = datetime.strptime(params.get('eta'), '%d%m%Y') if params.get('eta') else None
    contract.ship_to = params.get('ship_to')
    contract.surname = params.get('surname', "")
    contract.internal_comments_to_logistic = params.get('internal_comments_to_logistic', "")
    contract.external_comments_to_customer = params.get('external_comments_to_customer', "")
    if unloading_point:
        contract.unloading_point = unloading_point
    contract.incoterm = params.get('incoterms_1')
    contract.usage = params.get('usage')
    contract.usage_no = params.get('usage_no')
    contract.prc_group1 = params.get('prc_group1')
    contract.save()


def map_sap_contract_item(contract: migration_models.Contract, item_objs: dict, order_text_list, **kwargs):
    is_po_upload_flow = kwargs.get('is_po_upload_flow', False)
    list_po_codes = kwargs.get('list_po_codes', [])
    material_code = {k: v.get('matNo') for k, v in item_objs.items()}
    material_ids = list(
        migration_models.MaterialMaster.objects
        .filter(material_code__in=list(material_code.values()))
        .values_list('id', 'material_code')
    )

    quantity_unit = (
        master_models.Conversion2Master.objects
        .filter(material_code__in=list(material_code.values()))
        .values_list("material_code", "from_value", "to_unit")
        .all()
    )

    quantity_unit_mapped_objs = {
        f"{material_code}-{to_unit}": from_value
        for (material_code, from_value, to_unit) in list(quantity_unit)
    }
    list_contract_material = []
    list_contract_material_id = []
    contract_materials = migration_models.ContractMaterial.objects.filter(
        contract=contract)

    for item_no, v in item_objs.items():
        material_id = [mat_id for (mat_id, mat_code) in material_ids if mat_code == v.get('matNo')]
        # Uncomment this one in case SAP data is sync with EO, or customer don't want to see the error
        # Until then, only use 0007985657 to test (0001003615)
        if not material_id:
            continue
        material_id = material_id[0]

        remain_quantity = v.get('RemainQty', 0)
        remain_quantity_ex = v.get('remainQtyEx', 0)
        commission = (
            v.get("commission_zcm1")[0].get("conditionRate")
            if len(v.get("commission_zcm1", [])) > 0
            else None
        )
        commission_amount = (
            v.get("commission_zcm3")[0].get("conditionRate")
            if len(v.get("commission_zcm3", [])) > 0
            else None
        )
        com_unit = (
            v.get("commission_zcm3")[0].get("currency")
            if len(v.get("commission_zcm3", [])) > 0
            else None
        )

        price_per_unit = (
            v.get("conditions")[0].get("conditionRate")
            if len(v.get("conditions", [])) > 0
            else 0
        )
        "Random value that will need to confirm"
        rand_delivery_over = round(random.uniform(0.0, 10.0), 2)
        rand_delivery_under = round(random.uniform(rand_delivery_over, 99.9), 2)
        quantity_unit = quantity_unit_mapped_objs.get(
            f"{v.get('matNo')}-{v.get('salesUnit')}"
        )
        rand_total_quantity = v.get('targetQty', round(random.uniform(remain_quantity, remain_quantity + 100), 2))
        rand_weight = round(random.uniform(0.0, 10.0), 2)
        additional_remark = {}
        extract_item_text_data_sap_es14(mapping_code_for_contract_materials, order_text_list, additional_remark,
                                        item_no)
        param = {
            "item_no": item_no,
            "material_code": v.get('matNo'),
            "material_description": v.get("matDescription", ""),
            "contract_no": contract.code,
            "currency": v.get('currency', "THB"),
            "delivery_over": rand_delivery_over,
            "delivery_under": rand_delivery_under,
            "plant": v.get('plant', "7554"),
            # In the future, we will have 2 type of price for contract material (domestic and export)
            # TODO: Need to update this case and db structure
            "price_per_unit": price_per_unit,
            "quantity_unit": quantity_unit,
            "total_quantity": rand_total_quantity,
            "remaining_quantity": remain_quantity,
            "remaining_quantity_ex": remain_quantity_ex,
            "weight": v.get("targetQty", rand_weight),
            "weight_unit": v.get('salesUnit', "TON"),
            "payment_term": v.get('paymentTerm'),
            "condition_group1": v.get("conditionGroup1", ""),
            "commission": commission,
            "commission_amount": commission_amount,
            "com_unit": com_unit,
            "mat_type": v.get("matType", "81"),
            "mat_group_1": v.get("matGroup1", ""),
            "additional_remark": additional_remark.get('remark'),
            "is_active": True,
        }

        try:
            obj, _created = (
                migration_models.ContractMaterial.all_objects.update_or_create(
                    contract=contract,
                    material_id=material_id,
                    item_no=item_no,
                    defaults=param
                )
            )
            if v.get("matType") in MaterialType.MATERIAL_WITHOUT_VARIANT.value:
                if is_po_upload_flow:
                    if obj.material.material_code in list_po_codes:
                        update_variant_when_get_contract(material_id, v)
                else:
                    update_variant_when_get_contract(material_id, v)
            if not v.get("rejectReason") == "93":
                list_contract_material_id.append(obj.pk)

        except MultipleObjectsReturned:
            objects_data = migration_models.ContractMaterial.objects \
                .filter(contract=contract, material_id=material_id, item_no=item_no)
            objects_data.update(**param)
            if is_po_upload_flow:
                list_contract_material.extend([x for x in objects_data])
            list_contract_material_id.extend([x.pk for x in objects_data])

    update_active_for_missing_contract_materials(contract_materials, list_contract_material_id)
    return list_contract_material if is_po_upload_flow else list_contract_material_id


def get_sap_contract_items(sap_fn, contract_no, context: Union[dict, None] = None):
    param = {}
    order_id = context and context.get("order_id", None)
    log_val = {
        "orderid": order_id,
    }
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value, **log_val).request_mulesoft_get(
        SapEnpoint.ES_14.value + "/" + contract_no,
        param
    )
    return response


def sync_contract_material_variant(sap_fn, material_id, contract_id):
    response = get_sap_contract_material_detail(sap_fn, contract_id, material_id)

    response_data = response.get("data", [])

    if not response_data:
        return [], []

    product_list = response_data[0].get("productList")

    if not product_list:
        return [], []

    def mapping_standard_variant_type(item: dict):
        item.update({"variantType": "Standard"})
        return item

    def mapping_nonstandard_variant_type(item: dict):
        item.update({"variantType": "Non-Standard"})
        return item

    standard_variant = list(map(mapping_standard_variant_type, product_list[0].get("matStandard", [])))
    non_standard_variant = list(map(mapping_nonstandard_variant_type, product_list[0].get("matNonStandard", [])))

    sap_mapping_contract_material_variant(material_id, standard_variant, "Standard")
    sap_mapping_contract_material_variant(material_id, non_standard_variant, "Non-Standard")

    list_standard_code = list(map(lambda item: item.get("matCode") if item.get("markFlagDelete") is not True else None,
                                  product_list[0].get("matStandard", [])))
    list_non_standard_code = list(
        map(lambda item: item.get("matCode") if item.get("markFlagDelete") is not True else None,
            product_list[0].get("matNonStandard", [])))

    return list_standard_code, list_non_standard_code


def get_sap_contract_material_detail(sap_fn, contract_id, mat_id):
    pi_id = str(uuid.uuid1().int)
    material = migration_models.MaterialMaster.objects.get(pk=mat_id)
    contract = migration_models.Contract.objects.get(pk=contract_id)

    if material is None or contract is None:
        return {}

    param = {
        "piMessageId": pi_id,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "customerNo": contract.sold_to.sold_to_code,
        "product": [
            {
                "productCode": material.material_code
            }
        ]
    }
    uri = f"sales/materials/search"
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
        uri,
        param
    )
    return response


def sap_mapping_contract_material_variant(material_id, list_obj, variant_type, dict_materials={}):
    list_variant_code = list(map(lambda item: item.get("matCode"), list_obj))

    update_list_obj = []
    create_list_obj = []

    list_variant_objs = list(
        migration_models.MaterialVariantMaster.objects
        .filter(code__in=list_variant_code, variant_type=variant_type)
    )

    mapping_variant_id_code_obj = {item.code: item for item in list_variant_objs}

    for item in list_obj:
        mat_code = item.get("matCode")
        material_id_from_dict = None
        if not material_id:
            material: master_model.MaterialMaster = dict_materials.get(item.get("materialCode", ""), None)
            material_id_from_dict = material.id if material else None
        params = {
            "material_id": material_id or material_id_from_dict,
            "description_en": item.get("matDescriptionEN"),
            "description_th": item.get("matDescriptionTH"),
            "determine_type": item.get("matDetermineType", 'A001'),
            "key_combination": item.get("keyCombination", 'Material entered'),
            "propose_reason": item.get("proposeReason", '0005'),
            "sales_unit": item.get("saleUnit", 'ROL'),
            "status": item.get("matStatus", 'Active'),
            "type": item.get("matType", "81"),
            "valid_from": datetime.strptime(item.get("validFrom", '31/12/9999'), "%d/%m/%Y"),
            "valid_to": datetime.strptime(item.get("validTo", '31/12/9999'), "%d/%m/%Y"),
            "variant_type": item.get("variantType")
        }

        if mapping_variant_id_code_obj.get(mat_code) is None:
            if len(create_list_obj) == 10:
                migration_models.MaterialVariantMaster.objects.bulk_create(create_list_obj)
                create_list_obj = []
            new_data_param = {
                **params,
                "code": mat_code,
                "basis_weight": "125",
                "diameter": "117",
                "grade": "CA"
            }
            new_variant = migration_models.MaterialVariantMaster(
                **new_data_param
            )

            create_list_obj.append(new_variant)
        else:
            if len(update_list_obj) == 10:
                migration_models.MaterialVariantMaster.objects.bulk_update(update_list_obj, list(params.keys()))
                update_list_obj = []
            update_variant = mapping_variant_id_code_obj.get(mat_code)
            for key, value in params.items():
                setattr(update_variant, key, value)
            update_list_obj.append(update_variant)

    if len(update_list_obj) > 0:
        migration_models.MaterialVariantMaster.objects.bulk_update(update_list_obj, list(params.keys()))

    if len(create_list_obj) > 0:
        migration_models.MaterialVariantMaster.objects.bulk_create(create_list_obj)

    return list_variant_code


def call_sap_api_get_customer_contracts(info, kwargs):
    """
    Call SAP get contract for customer
    @param info:
    @param kwargs: {
        'sold_to_id': '6190',
        'filter': {'company_ids': [1, 5, 2, 6]},
        'sort_by': {'direction': '', 'field': ['code']},
        'first': 50
    }
    @return: Boolean
    """
    try:
        sold_to_id = kwargs.get("sold_to_id")
        sold_to = master_models.SoldToMaster.objects.get(id=sold_to_id)
        customer_no = sold_to.sold_to_code

        sale_org_list = []
        company_ids = kwargs["filter"]["company_ids"]  # get company list from filter (checkboxes in page create order)

        # if user not select any company frontend will send company_ids = [-1]
        # so if company_ids != [-1], we need to check company_ids
        if company_ids != [-1]:
            # get company code from company master by company id
            sale_org_list = [{"saleOrg": master_models.CompanyMaster.objects.filter(id=id).first().code} for id in
                             company_ids]

        current_date = datetime.now().strftime("%d/%m/%Y")

        params = {
            "piMessageId": str(uuid.uuid1().int),
            "customerNo": customer_no,
            "validFrom": current_date,
            "validTo": current_date,
            "saleOrgList": sale_org_list,
            "docType": "ZCQ",
        }

        rs = call_sap_api(info, SapEnpoint.ES_13.value, SapEnpoint.METHOD_POST.value, params)

        # If there aren't any contract from SAP
        if not rs:
            return False

        list_contract_code = [contract.get("contractNo") for contract in rs]
        kwargs.update({
            "sap_code": list_contract_code
        })
        sap_contract_mapping(rs)

        if not kwargs.get("contract_no"):
            return True

        contract_no = kwargs.get("contract_no")[0]
        for item in rs:
            # Case API found contractNo
            if item.get("contractNo") == contract_no:
                return True

        # Case API didn't find contractNo
        return False
    except Exception:
        return False


def resolve_variants(root, info):
    def get_sorted_variants(variants, sorted_material_codes):
        dict_variants = {}
        rs_variants = []
        for variant in variants:
            dict_variants[variant.code] = variant
        for code in sorted_material_codes:
            if variant := dict_variants.get(code):
                rs_variants.append(variant)
        return rs_variants

    if (
            info.variable_values.get("list_standard_variants") is not None and
            info.variable_values.get("list_non_standard_variants") is not None
    ):
        sorted_material_codes = info.variable_values.get("list_standard_variants") + info.variable_values.get(
            "list_non_standard_variants")
        # TODO: check distinct this agg function
        # OLD version: distinct()
        variants = migration_models.MaterialVariantMaster.objects.filter(
            Q(code__in=info.variable_values.get("list_standard_variants"), variant_type="Standard") |
            Q(code__in=info.variable_values.get("list_non_standard_variants"), variant_type="Non-Standard")
        ).annotate(
            calculation=Subquery(
                master_models.Conversion2Master.objects.filter(
                    material_code=OuterRef('code'), to_unit='ROL'
                ).distinct("material_code").values('calculation'),
            )
        ).order_by("description_th")

        return get_sorted_variants(variants, sorted_material_codes)

    if info.variable_values.get("material_variants_sap", None):
        variants = info.variable_values.get("material_variants_sap").get(root.material_code, {})

        is_data_from_es15 = variants.get("data_from_es15", True)

        if not is_data_from_es15:
            material_id = variants.get("material_id", None)
            return migration_models.MaterialVariantMaster.objects.filter(material__id=material_id)

        sorted_material_codes = (
                variants.get("list_standard_variant", []) +
                variants.get("list_non_standard_variant", [])
        )
        queryset = migration_models.MaterialVariantMaster.objects.filter(
            Q(code__in=variants.get("list_standard_variant", []), variant_type="Standard") |
            Q(code__in=variants.get("list_non_standard_variant", []), variant_type="Non-Standard")
        )
        return get_sorted_variants(queryset, sorted_material_codes)

    return migration_models.MaterialVariantMaster.objects.filter(material_id=root.id)


def update_variant_when_get_contract(material_id, es_14_item):
    """
    Apply for material type as 81 or 82
    Delete all needless variants
    @param material_id:
    @param es_14_item:
    @return:
    """
    material_code = es_14_item.get("matNo")
    material = master_models.MaterialMaster.objects.filter(id=material_id).first()
    param = {
        "material_id": material_id,
        "description_en": es_14_item.get("matDescription"),
        "determine_type": es_14_item.get("matDetermineType", 'A001'),
        "sales_unit": es_14_item.get("salesUnit",
                                     '') if material.material_group == MaterialGroup.PK00.value or is_default_sale_unit_from_contract(
            es_14_item.get("matGroup1")) else 'ROL',
        "type": es_14_item.get("matType", "81"),
        "code": material_code,
        "basis_weight": material_code[6:9],
        "diameter": material_code[14:17],
        "grade": material_code[3:6].strip("-")
    }
    migration_models.MaterialVariantMaster.objects.update_or_create(
        material_id=material_id,
        code=material_code,
        defaults=param
    )
    migration_models.MaterialVariantMaster.objects.filter(
        material_id=material_id
    ).exclude(
        code=material_code
    ).delete()


def resolve_search_suggestion_domestic_sold_tos(account_groups):
    qs = master_models.SoldToMaster.objects.filter(account_group_code__in=account_groups, sold_to_code__in=Subquery(
        master_models.SoldToChannelMaster.objects.filter(distribution_channel_code__in=["10", "20"]).distinct(
            "sold_to_code").values("sold_to_code")
    ))
    return qs


def resolve_search_suggestion_domestic_ship_tos():
    qs = master_models.SoldToPartnerAddressMaster.objects.all()
    return qs


def call_es15_get_list_detail(sap_fn, sold_to_code: str, material_codes: list):
    pi_message_id = str(uuid.uuid1().int)

    param = {
        "piMessageId": pi_message_id,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "customerNo": sold_to_code,
        "product": [
            {
                "productCode": material_code
            } for material_code in material_codes
        ]
    }
    uri = "sales/materials/search"
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
        uri,
        param
    )
    return response


def sync_contract_material_variant_v2(sap_fn, material_ids: list, sold_to_code: str):
    dict_materials = (
        master_model.MaterialMaster.objects
        .filter(id__in=material_ids)
        .in_bulk(field_name="material_code")
    )

    response = call_es15_get_list_detail(sap_fn, sold_to_code, dict_materials.keys())

    response_data = response.get("data", [])

    if not response_data:
        return [], []

    product_list = response_data[0].get("productList")

    if not product_list:
        return [], []

    def _reduce_list_mat_variants(prev, next):
        material_code = next.get("productCode", "")
        for item in next.get("matStandard", []):
            prev["matStandard"].append({**item, "variantType": "Standard", "materialCode": material_code})
        for item in next.get("matNonStandard", []):
            prev["matNonStandard"].append({**item, "variantType": "Non-Standard", "materialCode": material_code})
        return prev

    list_material_variants: dict = reduce(_reduce_list_mat_variants, product_list,
                                          {"matStandard": [], "matNonStandard": []})

    sap_mapping_contract_material_variant(None, list_material_variants.get("matStandard", []), "Standard",
                                          dict_materials)
    sap_mapping_contract_material_variant(None, list_material_variants.get("matNonStandard", []), "Non-Standard",
                                          dict_materials)

    list_standard_code = list(
        map(
            lambda item: item.get("matCode") if item.get("markFlagDelete") is not True else None,
            list_material_variants.get("matStandard", [])
        )
    )
    list_non_standard_code = list(
        map(
            lambda item: item.get("matCode") if item.get("markFlagDelete") is not True else None,
            list_material_variants.get("matNonStandard", [])
        )
    )

    return list_standard_code, list_non_standard_code


def resolve_material_suggestion(qs):
    return master_models.MaterialMaster.objects.filter(material_code__in=qs)


def search_suggestion_sold_tos_cust_mat(account_group_code, distribution_channel_code):
    qs = master_models.SoldToMaster.objects.filter(account_group_code__in=account_group_code, sold_to_code__in=Subquery(
        master_models.SoldToChannelMaster.objects.filter(
            distribution_channel_code__in=distribution_channel_code).distinct(
            "sold_to_code").values("sold_to_code")
    ))
    return qs


def resolve_sale_organization_by_sold_to(sold_to):
    qs = master_model.SoldToChannelMaster.objects.filter(
        sold_to_code=sold_to,
    ).values("sales_organization_code", "distribution_channel_code").distinct()

    if qs:
        sales_org_dist_channel_dict = {}
        dist_channel_sale_org_dict = {}
        sales_org_set = set()
        dist_channel_set = set()
        sales_org_by_dist_channel_res = []
        dist_channel_by_sales_org_res = []
        for sold_to in qs:
            sales_org_set.add(sold_to.get('sales_organization_code', ""))
            dist_channel_set.add(sold_to.get('distribution_channel_code', ""))
            sales_org_dist_channel_dict.setdefault(sold_to.get('sales_organization_code', ""), set()).add(
                sold_to.get('distribution_channel_code', ""))
            dist_channel_sale_org_dict.setdefault(sold_to.get('distribution_channel_code', ""), set()).add(
                sold_to.get('sales_organization_code', ""))

        for key, values in sales_org_dist_channel_dict.items():
            values_db = get_distribution_channels_by_codes(values)
            sales_org_by_dist_channel_res.append({
                "sales_org": key,
                "distribution_channel": values_db
            })

        for key, values in dist_channel_sale_org_dict.items():
            values_db = get_sales_orgs_by_codes(values)
            dist_channel_by_sales_org_res.append({
                "distribution_channel": key,
                "sales_org": values_db
            })

        return {
            "sales_organization": get_sales_orgs_by_codes(sales_org_set),
            "distribution_channel": get_distribution_channels_by_codes(dist_channel_set),
            "sales_org_by_dist_channel": sales_org_by_dist_channel_res,
            "dist_channel_by_sales_org": dist_channel_by_sales_org_res
        }
    return {}
