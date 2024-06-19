import django_filters

from saleor.graphql.core.filters import MetadataFilterBase
from saleor.graphql.core.types import FilterInputObjectType
from sap_master_data import models as master_models

def search_cip_header_ship_tos(qs, _, value):
    if not value:
        return qs
    address_code_list = master_models.SoldToChannelPartnerMaster.objects.filter(partner_code__icontains=value,
                                                                                partner_role="WE").distinct(
        "address_link").values(
        "address_link")
    qs = qs.filter(address_code__in=address_code_list, partner_code__isnull=False)
    return qs


class CipHeaderShipTosFilter(MetadataFilterBase):
    search = django_filters.CharFilter(method=search_cip_header_ship_tos)

    class Meta:
        model = master_models.SoldToPartnerAddressMaster
        fields = ["id"]


class CipHeaderShipTosFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CipHeaderShipTosFilter
