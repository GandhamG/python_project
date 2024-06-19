from sap_migration.models import OrderOtcPartner, OrderOtcPartnerAddress
from scg_checkout.graphql.enums import RealtimePartnerType


class OrderOtcPartnerAddressRepo:
    @classmethod
    def save_otc_partner_address(cls, data):
        if isinstance(data, OrderOtcPartnerAddress):
            otc_partner_address = data
        else:
            otc_partner_address = OrderOtcPartnerAddress(**data)
        otc_partner_address.save()
        return otc_partner_address

    @classmethod
    def delete_otc_partner_address(cls, otc_partner_address):
        otc_partner_address.delete()

    @classmethod
    def get_order_otc_ship_to_by_id(cls, order_id):
        return OrderOtcPartner.objects.filter(
            order_id=order_id, partner_role=RealtimePartnerType.SHIP_TO.value
        ).first()
