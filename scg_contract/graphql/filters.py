import django_filters

from saleor.graphql.core.types import FilterInputObjectType
from saleor.graphql.utils.filters import filter_by_query_param
from scg_contract import models


def filter_search_contract(qs, _, value):
    search_fields = ["project_name", "company__name", "bu__name"]
    if value:
        qs = qs.select_related("company", "bu")
        qs = filter_by_query_param(qs, value, search_fields)
    return qs


class ContractFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method=filter_search_contract)

    class Meta:
        model = models.Contract
        fields = ["project_name"]


class ContractFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ContractFilter
