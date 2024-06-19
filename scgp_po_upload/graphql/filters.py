import django_filters

import sap_master_data.models
from saleor.graphql.core.filters import MetadataFilterBase
from saleor.graphql.core.types import FilterInputObjectType
from scgp_po_upload.models import PoUploadCustomerSettings


def suggestion_search_sold_to(qs, _, value):
    if not value:
        return qs
    sold_to_added = PoUploadCustomerSettings.objects.all().values_list('sold_to_id', flat=True)
    return qs.filter(sold_to_code__icontains=value).exclude(id__in=sold_to_added)


class SoldToMasterFilter(MetadataFilterBase):
    sold_to = django_filters.CharFilter(method=suggestion_search_sold_to)

    class Meta:
        model = sap_master_data.models.SoldToMaster
        fields = ["id"]


class SoldToMasterFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = SoldToMasterFilter
