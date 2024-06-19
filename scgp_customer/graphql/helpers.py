import uuid

from sap_master_data import models as sap_master_data_models
from sap_master_data.models import SoldToPartnerAddressMaster
from scg_checkout.graphql.enums import SalesOrgCode
from scgp_require_attention_items.graphql.helper import fill_zeros_prepare_param

def prepare_es25_params(data_input):
    create_date_from = ""
    create_date_to = ""
    update_date_from = ""
    update_date_to = ""
    if create_date_from_obj := data_input.get("create_date_from"):
        create_date_from = create_date_from_obj.strftime("%d/%m/%Y")
    if create_date_to_obj := data_input.get("create_date_to"):
        create_date_to = create_date_to_obj.strftime("%d/%m/%Y")
    if update_date_from_obj := data_input.get("update_date_from"):
        update_date_from = update_date_from_obj.strftime("%d/%m/%Y")
    if update_date_to_obj := data_input.get("update_date_to"):
        update_date_to = update_date_to_obj.strftime("%d/%m/%Y")
    sales_org_list = []
    if data_input.get("company") is None:
        sale_org_all = sap_master_data_models.SalesOrganizationMaster.objects.all()
        for sale_org in sale_org_all:
            sales_org_list.append({
                "salesOrg": sale_org.code,
                "distributionChannel": "10"
            })
    else:
        sales_org_list.append({
            "salesOrg": data_input.get("company"),
            "distributionChannel": "10"
        })

    params = {
        "piMessageId": str(uuid.uuid1().int),
        "createDateFrom": create_date_from,
        "createDateTo": create_date_to,
        "requestDateFrom": update_date_from,
        "requestDateTo": update_date_to,
        "salesOrgList": sales_org_list,
        "flgItem": "X",
    }
    if data_input.get("sold_to", None):
        params["customerList"] = [
            {
                "customer": data_input.get("sold_to", "").split("-")[0].strip()
            }
        ]
    if data_input.get("material_code", None):
        params["material"] = data_input.get("material_code", "")
    if data_input.get("so_no", None):
        params["salesOrderNo"] = data_input.get("so_no", "")
    if data_input.get("contract_no", None):
        params["contractNo"] = data_input.get("contract_no", "")
    if data_input.get("dp_no", None):
        params["dpNo"] = fill_zeros_prepare_param(data_input.get("dp_no", ""))
    if data_input.get("invoice_no", None):
        params["billingNo"] = data_input.get("invoice_no", "")
    if data_input.get("purchase_order_no", None):
        params["customerPoNo"] = data_input.get("purchase_order_no", "")

    params = {key: val for key, val in params.items() if val != ""}
    return params


def get_qty_ton_by_material_code(material_code, quantity):
    conversion = sap_master_data_models.Conversion2Master.objects.filter(
        material_code=material_code
    ).first()
    if not conversion:
        return 0
    calculation = conversion.calculation
    order_quantity_ton = float(quantity) * float(calculation) / 1000
    return order_quantity_ton


def get_sale_org_name_by_code(code):
    if code == SalesOrgCode.SKIC.value:
        return "บริษัท สยามคราฟท์อุตสาหกรรม จำกัด"
    if code == SalesOrgCode.THAI.value:
        return "บริษัท ไทยเคนเปเปอร์ จำกัด (มหาชน)"
    return ""


def get_sold_to_data_from_es26(data):
    if not data:
        return None

    order_partner = data[0].get("orderPartners", [])
    sold_to_name = []
    sold_to_address = []
    for partner in order_partner:
        if partner.get("partnerRole", "") == "AG":
            for address in partner["address"]:
                street = address.get("street", "")
                district = partner.get("district", "")
                city = partner.get("city", "")
                post_code = partner.get("postCode", "")
                sold_to_name.append(address.get("name", ""))
                sold_to_address.append(f"{street} {district} {city} {post_code}")
            return {
                "sold_to_name": '\n'.join(sold_to_name),
                "sold_to_address": '\n'.join(sold_to_address),
            }
    return None


def get_ship_to_data_from_es26(data):
    if not data:
        return None

    order_partner = data[0].get("orderPartners", [])
    for partner in order_partner:
        if partner.get("partnerRole", "") == "WE":
            partner_no = partner.get("partnerNo", "")
            address_link = partner.get("addrLink", "")
            ship_to = SoldToPartnerAddressMaster.objects.filter(
                sold_to_code=partner_no,
                address_code=address_link
            ).first()
            if not ship_to:
                return None
            return {
                "bill_to_name": ship_to.name1,
                "bill_to_address": f"{ship_to.street} {ship_to.district} {ship_to.city} {ship_to.postal_code}",
            }
    return None


def get_bill_to_data_from_es26(data):
    order_partner = data.get("orderPartners", [])
    bill_to_name = []
    bill_to_address = []
    for partner in order_partner:
        if partner.get("partnerRole", "") == "RE":
            for address in partner["address"]:
                street = address.get("street", "")
                district = partner.get("district", "")
                city = partner.get("city", "")
                post_code = partner.get("postCode", "")
                bill_to_name.append(address.get("name", ""))
                bill_to_address.append(f"{street} {district} {city} {post_code}")

            return {
                "bill_to_name": '\n'.join(bill_to_name),
                "bill_to_address": '\n'.join(bill_to_address),
            }
    return None
