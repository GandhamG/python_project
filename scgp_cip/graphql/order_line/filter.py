from saleor.graphql.core.filters import MetadataFilterBase
from saleor.graphql.core.types import FilterInputObjectType
import django_filters
from sap_master_data.models import MaterialMaster
from django.db.models import Value, F, Subquery, OuterRef
from django.db.models.functions import Concat


def search_materials_by_mat_code_or_desc(qs, _, value):
    all_data = qs.annotate(search_text=Concat(F("material_code"), Value(' - '),
                                              F("description_en")))
    qs = all_data.filter(search_text__icontains=value).distinct()
    return qs


def search_materials_by_cust_mat_code_or_desc(qs, _, value):
    all_data = qs.annotate(description_en=Subquery(MaterialMaster.objects.filter(
        material_code=OuterRef("material_code")).distinct("material_code").values("description_en")[:1])) \
        .annotate(search_text=Concat(F("sold_to_material_code"), Value(' - '), F('description_en')))
    qs = all_data.filter(search_text__icontains=value).distinct()
    return qs


class MaterialSearchFilter(MetadataFilterBase):
    mat_code = django_filters.CharFilter(method=search_materials_by_mat_code_or_desc)
    cust_mat_code = django_filters.CharFilter(method=search_materials_by_cust_mat_code_or_desc)


class MaterialSearchFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = MaterialSearchFilter
