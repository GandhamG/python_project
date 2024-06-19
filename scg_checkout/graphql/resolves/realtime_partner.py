from sap_master_data.models import SoldToPartnerAddressMaster, SoldToChannelPartnerMaster


def resolve_realtime_partner_address(partner_code, partner_role):
    partner = SoldToChannelPartnerMaster.objects.filter(partner_code=partner_code, partner_role=partner_role).first()
    if partner is None:
        return None
    
    partner_address = SoldToPartnerAddressMaster.objects.filter(address_code=partner.address_link).first()
    if partner_address is None:
        return None
    
    return f"{partner_address.street}, {partner_address.district}, {partner_address.city}"