import pytest

from sap_master_data.models import SoldToPartnerAddressMaster


@pytest.fixture
def sap_master_data_sold_to_partner():
    partner = [
        SoldToPartnerAddressMaster(
            partner_code="0000000001", email="0000000001@email.com"
        ),
        SoldToPartnerAddressMaster(
            partner_code="0000000002", email="0000000002@email.com"
        ),
        SoldToPartnerAddressMaster(
            partner_code="0000000003", email="0000000003@email.com"
        ),
    ]
    return SoldToPartnerAddressMaster.objects.bulk_create(partner)
