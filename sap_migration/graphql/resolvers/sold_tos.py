from sap_master_data.models import (
    SoldToPartnerAddressMaster,
    SoldToTextMaster,
    SoldToChannelPartnerMaster,
)
from scgp_po_upload.models import PoUploadCustomerSettings


def resolve_sold_to_address_text(sold_to):
    try:
        address = ""
        partner_role = "AG"
        sold_to_code = sold_to.sold_to_code
        sold_to_channel_partner = SoldToChannelPartnerMaster.objects.filter(
            sold_to_code=sold_to_code,
            partner_code=sold_to_code,
            partner_role=partner_role).first()
        if sold_to_channel_partner:
            address_link = sold_to_channel_partner.address_link
            partner_code = sold_to_channel_partner.partner_code
            sold_to_partner_address = SoldToPartnerAddressMaster.objects.filter(
                sold_to_code=sold_to_code,
                address_code=address_link,
                partner_code=partner_code
            ).first()

            address = f"{sold_to_partner_address.street} {sold_to_partner_address.district} " \
                      f"{sold_to_partner_address.city} {sold_to_partner_address.postal_code}"

        return address


    except Exception:
        return None


def resolve_representatives(sold_to):
    return sold_to.user.all()


def resolve_internal_comments_to_warehouse(root):
    try:
        sold_to_code = root.sold_to_code
        sold_to_text = SoldToTextMaster.objects.filter(sold_to_code=sold_to_code, text_id="Z001").first()
        internal_comments_to_warehouse = sold_to_text.text_line

        return internal_comments_to_warehouse

    except Exception:
        return ""


def resolve_external_comments_to_customer(root):
    try:
        sold_to_code = root.sold_to_code
        sold_to_text = SoldToTextMaster.objects.filter(sold_to_code=sold_to_code, text_id="Z004").first()
        external_comments_to_customer = sold_to_text.text_line

        return external_comments_to_customer

    except Exception:
        return ""


def resolve_show_po_upload(sold_to):
    if PoUploadCustomerSettings.objects.filter(sold_to=sold_to):
        return True
    return False
