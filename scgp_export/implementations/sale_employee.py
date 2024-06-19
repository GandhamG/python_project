import json
import uuid

from django.core.exceptions import MultipleObjectsReturned

from sap_master_data.models import SoldToChannelPartnerMaster
from sap_migration.graphql.enums import OrderType
from sap_migration.models import Order
from scg_checkout.graphql.enums import RealtimePartnerType
from scgp_export.graphql.enums import SapEnpoint


def save_sale_employee_partner_data(order: Order, plugin):
    sold_to_code = order.sold_to.sold_to_code

    """If order is from customer, using saleOrg, division, distchannel code from contract"""
    """https://scgdigitaloffice.atlassian.net/browse/SEO-1110?focusedCommentId=96916"""
    try:
        if order.type == OrderType.CUSTOMER.value:
            sale_organization_code = order.contract.sales_organization.code
            distribution_channel_code = order.contract.distribution_channel.code
            division_code = order.contract.division.code
        else:
            sale_organization_code = order.sales_organization.code
            distribution_channel_code = order.distribution_channel.code
            division_code = order.division.code
    except AttributeError:
        return False

    body = {
        "piMessageId": str(uuid.uuid1().int),  # Mocked up data, this is not important
        "customerId": sold_to_code,
        "saleOrg": sale_organization_code,
    }
    example_data = {}
    response = plugin.call_api_sap_client(
        "scg.sap_client_api",
        SapEnpoint.ES_08.value,
        "POST",
        json.dumps(body),
        example_data,
    )

    try:
        result = list(
            filter(
                (
                    lambda item: item["partnerFunction"]
                    == RealtimePartnerType.SALE_EMPLOYEE.value
                    and item["distributionChannel"] == distribution_channel_code
                    and item["division"] == division_code
                ),
                response["data"][0]["partnerList"],
            )
        )
    except Exception:
        result = list()

    if len(result) > 0:
        partner_data = result[0]

        try:
            _, created = SoldToChannelPartnerMaster.objects.get_or_create(
                sold_to_code=sold_to_code,
                sales_organization_code=sale_organization_code,
                distribution_channel_code=distribution_channel_code,
                division_code=division_code,
                partner_code=partner_data.get("partnerNo"),
                partner_role=partner_data.get("partnerFunction"),
            )
        except MultipleObjectsReturned:
            return True
        return created

    return False
