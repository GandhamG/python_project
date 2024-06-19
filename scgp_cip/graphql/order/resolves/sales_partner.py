import logging

from django.core.exceptions import ImproperlyConfigured

from saleor.graphql.core.connection import filter_connection_queryset, create_connection_slice
from sap_migration.models import SalesOfficeMaster, SalesGroupMaster
from scg_checkout.graphql.enums import PaymentTerm
from scg_checkout.graphql.helper import PAYMENT_TERM_MAPPING
from scgp_cip.common.constants import OTC_ACCOUNT_GROUPS, PP_SOLD_TO_ACCOUNT_GROUPS, SHIP_SEARCH_ACCOUNT_GRP, \
    CIP_SOLD_TO_ACCOUNT_GROUPS, CIP, DEFAULT_OTC_SOLD_TO_CODE
from scgp_cip.common.enum import CIPOrderPaymentType
from scgp_cip.dao.order.sale_organization_master_repo import SalesOrganizationMasterRepo
from scg_checkout.graphql.types import DomesticSoldToCountableConnection
from scgp_cip.dao.order.sold_to_master_repo import SoldToMasterRepo
from scgp_cip.dao.order.distribution_channel_master_repo import DistributionChannelMasterRepo
from scgp_cip.dao.order.division_master_repo import DivisionMasterRepo
from scgp_cip.graphql.order.types import PaymentTermData
from scgp_cip.service.helper.create_order_helper import get_text_master_data_by_sold_to_code
from scgp_customer.graphql.resolvers.customer_contract import resolve_unloading_point
from scgp_user_management.graphql.resolvers.scgp_users import resolve_default_sales_organizations, \
    resolve_scgp_distribution_channels_by_user, resolve_scgp_divisions_by_user, resolve_scgp_sales_groups_by_user
from scgp_cip.service.integration.integration_service import get_partner_info


def resolve_search_suggestion_sold_tos_cip(info, kwargs):
    sale_org = kwargs.get("sale_org", None)
    distribution_channel = kwargs.get("distribution_channel", None)
    division = kwargs.get("division", None)
    if kwargs.get("one_time_customer", False):
        account_groups = OTC_ACCOUNT_GROUPS
    else:
        bu = SalesOrganizationMasterRepo.get_bu_by_sale_org(sale_org)
        account_groups = CIP_SOLD_TO_ACCOUNT_GROUPS if bu == CIP else PP_SOLD_TO_ACCOUNT_GROUPS
    qs = SoldToMasterRepo.get_by_sales_info(sale_org, distribution_channel, division, account_groups)
    qs = filter_connection_queryset(qs, kwargs)
    return create_connection_slice(
        qs, info, kwargs, DomesticSoldToCountableConnection
    )


def resolve_get_sales_data(info, kwargs):
    channel_type = kwargs.get("distribution_channel_type", None)
    scgp_user = info.context.user.scgp_user
    default_sales_organization = resolve_default_sales_organizations(scgp_user.pk)
    sale_org_filter = kwargs.get("sale_org") if kwargs and kwargs.get("sale_org", False) \
        else default_sales_organization.code if default_sales_organization and default_sales_organization.code else False
    if sale_org_filter:
        distribution_channel = DistributionChannelMasterRepo.get_distribution_channel_by_sale_org_code(sale_org_filter,
                                                                                                       channel_type)
        division = DivisionMasterRepo.get_division_by_sale_org_code(sale_org_filter)
    else:
        distribution_channel = resolve_scgp_distribution_channels_by_user(scgp_user.pk)
        division = resolve_scgp_divisions_by_user(scgp_user.pk)
    return {
        "sales_organization": SalesOrganizationMasterRepo.get_sales_org_by_user_order_by_bu(scgp_user.pk),
        "default_sales_organization": default_sales_organization,
        "distribution_channel": distribution_channel,
        "division": division,
        "default_otc_sold_to": SoldToMasterRepo.get_sold_to_data(DEFAULT_OTC_SOLD_TO_CODE)
    }


def resolve_payment_term():
    payment_term_list = []
    for key in PAYMENT_TERM_MAPPING:
        val = PAYMENT_TERM_MAPPING[key]
        payment_term_list.append(
            PaymentTermData(
                code=key,
                name=val,
                displayText=key + "-" + val
            ),
        )
    return payment_term_list


def resolve_unloading_points(ship_to_address):
    ship_to = list(ship_to_address)[0] if len(ship_to_address) != 0 \
        else None
    result = []
    if ship_to:
        result = resolve_unloading_point(ship_to.partner_code)
    return result


def resolve_ship_to_and_bill_to_addresses(data):
    try:
        response = get_partner_info(data)
    except Exception as e:
        logging.exception(f"Call ES-08 Exception: for sold to  {data.sold_to_code}")
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)
    ship_to_list = []
    bill_to_list = []
    if response and "partnerList" in response:
        ship_to_result = list(filter(lambda item: item["partnerFunction"] == "WE", response["partnerList"]))
        bill_to_result = list(filter(lambda item: item["partnerFunction"] == "RE", response["partnerList"]))
        for ship_to in ship_to_result:
            partner_code = ship_to.get("partnerNo")
            sold_to_partner_address = SoldToMasterRepo.get_sold_to_partner_address(data.sold_to_code,
                                                                                   partner_code)
            ship_to_list.append(sold_to_partner_address) if sold_to_partner_address else None

        for bill_to in bill_to_result:
            partner_code = bill_to.get("partnerNo")
            sold_to_partner_address = SoldToMasterRepo.get_sold_to_partner_address(data.sold_to_code,
                                                                                   partner_code)
            bill_to_list.append(sold_to_partner_address) if sold_to_partner_address else None

    return ship_to_list, bill_to_list


def resolve_sales_employee(sold_to, sale_org, distribution_channel, division):
    channel_partner = get_channel_partner(sold_to, "VE", sale_org, distribution_channel, division)
    return channel_partner.partner_code if channel_partner else None


def get_channel_partner(sold_to_code, partner_role, sale_org, distribution_channel, division):
    try:
        sold_to_channel_partner = SoldToMasterRepo.get_sold_to_channel_partner(sold_to_code, partner_role, sale_org,
                                                                               distribution_channel, division).first()

        return sold_to_channel_partner
    except Exception:
        return None


def resolve_search_suggestion_ship_to_cip(info, kwargs):
    sold_to = kwargs.get("sold_to", None)
    sale_org = kwargs.get("sale_org", None)
    distribution_channel_code = kwargs.get("distribution_channel", None)
    division_code = kwargs.get("division", None)
    try:
        qs = SoldToMasterRepo.fetch_ship_tos_excluding_selected_ship_to(SHIP_SEARCH_ACCOUNT_GRP, sold_to, "WE",
                                                                        sale_org,
                                                                        distribution_channel_code, division_code)
        return qs

    except Exception:
        return None
def fetch_sale_group_and_add_empty_item(scgp_user):
    sale_group = list(resolve_scgp_sales_groups_by_user(scgp_user).all())
    empty_sales_group = SalesGroupMaster()
    empty_sales_group.code = ''
    empty_sales_group.name = ''
    sale_group.append(empty_sales_group)
    return sale_group

def resolve_sold_to_header_info_cip(info, kwargs):
    sold_to_code = kwargs.get("sold_to", None)
    sales_org = kwargs.get("sale_org", None)
    distribution_channel = kwargs.get("distribution_channel", None)
    division = kwargs.get("division", None)
    scgp_user = info.context.user.scgp_user
    channel_master_data = SoldToMasterRepo.get_sold_to_channel_master(sold_to_code, sales_org, distribution_channel,
                                                                      division).first()
    payment_term = resolve_payment_term()
    order_type = None
    def_payment_term: PaymentTermData = None
    ship_to_address, unloading_points, bill_to_address = [], [], []
    if channel_master_data:
        if channel_master_data.payment_term:
            order_type = CIPOrderPaymentType.CASH.value if channel_master_data.payment_term in [PaymentTerm.DEFAULT.value, PaymentTerm.AP00.value] \
                else CIPOrderPaymentType.CREDIT.value
            def_payment_term = {
                "code": channel_master_data.payment_term,
                "name": PAYMENT_TERM_MAPPING[channel_master_data.payment_term],
                "displayText": channel_master_data.payment_term + "-" + PAYMENT_TERM_MAPPING[
                    channel_master_data.payment_term]
            }

        ship_to_address, bill_to_address = resolve_ship_to_and_bill_to_addresses(channel_master_data)
        unloading_points = resolve_unloading_points(ship_to_address)
    text_master_data = get_text_master_data_by_sold_to_code(sold_to_code, sales_org, distribution_channel, division)
    sale_group= fetch_sale_group_and_add_empty_item(scgp_user)
    return {
        "sold_to": SoldToMasterRepo.get_sold_to_data(sold_to_code),
        "order_type": order_type,
        "tax_classification": channel_master_data.taxkd if channel_master_data else None,
        "ship_to": ship_to_address,
        "bill_to": bill_to_address,
        "payment_term": payment_term,
        "unloading_points": unloading_points,
        "sale_employee": resolve_sales_employee(sold_to_code, sales_org, distribution_channel, division),
        "sale_organization": SalesOrganizationMasterRepo.get_sale_organization_by_code(sales_org),
        "sale_group": sale_group,
        "sale_office": SalesOfficeMaster.objects.filter(scgpuser__id=scgp_user.id),
        "division": DivisionMasterRepo.get_division_by_code(division),
        "distribution_channel": DistributionChannelMasterRepo.get_distribution_channel_by_code(
            distribution_channel),
        "default_sale_group": sale_group[0],
        "default_unloading_point": list(unloading_points)[0] if len(unloading_points) != 0
        else None,
        "default_ship_to": list(ship_to_address)[0] if len(ship_to_address) != 0
        else None,
        "default_bill_to": list(bill_to_address)[0] if len(bill_to_address) != 0
        else None,
        "default_payment_term": def_payment_term if def_payment_term else None,
        "headerNote1_en": text_master_data.get("0002_EN") if text_master_data else None,
        "commentsToWarehouse_en": text_master_data.get("Z001_EN") if text_master_data else None,
        "headerNote1_th": text_master_data.get("0002_TH") if text_master_data else None,
        "commentsToWarehouse_th": text_master_data.get("Z001_TH") if text_master_data else None,
    }
