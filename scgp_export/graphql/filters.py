import django_filters

from sap_master_data.models import SoldToMaster
from sap_migration.models import Contract
from scg_checkout.graphql.helper import update_date_range_with_timezone
from scg_checkout.models import SalesOrganization
from saleor.graphql.utils.filters import filter_range_field
from scgp_export.graphql.enums import (
    ScgpExportOrderStatus,
    ScgpExportOrderStatusSAP
)
from django.db.models import (
    Q,
    F, OuterRef, Subquery
)
from django.db.models import Value
from django.db.models.functions import (
    Concat,
    Replace
)
from saleor.graphql.core.filters import (
    MetadataFilterBase,
    ListObjectTypeFilter,
    ObjectTypeFilter,
)
from saleor.graphql.core.types import (
    FilterInputObjectType,
    DateRangeInput,
)

from sap_migration import models as sap_migration_models
from sap_master_data import models as sap_data_models


def filter_export_pi_by_code(qs, _, value):
    if not value:
        return qs
    return qs.filter(code__icontains=value)


def filter_pi(qs, _, value):
    sold_external_codes = sap_data_models.SoldToExternalMaster.objects.annotate(
        search_text=Concat('sold_to_code', Value(' - '), 'sold_to_name')
    ).filter(search_text__icontains=value).values_list('sold_to_code', flat=True).distinct()

    qs = qs.filter(
        Q(sold_to__sold_to_code__in=sold_external_codes) | Q(contract__code__ilike=value)).distinct()
    return qs


def search_export_sold_to_by_code_or_name(qs, _, value):
    all_data = qs.annotate(
        name=Subquery(
            sap_data_models.SoldToPartnerAddressMaster.objects.filter(
                partner_code=OuterRef('sold_to_code')
            ).distinct("partner_code").annotate(
                new_name=Concat(F('name1'), Value(' '), F('name2'), Value(' '), F('name3'),
                                Value(' '), F('name4'))).values('new_name')[:1])) \
        .annotate(full_name=Concat(F("sold_to_code"), Value(' - '), F('name')))
    qs = all_data.filter(full_name__icontains=value).distinct()
    return qs


def search_ship_to_by_input(qs, _, value):
    if not value:
        return qs
    return qs.filter(
        pk__in=Subquery(
            sap_migration_models.Order.objects.filter(ship_to__icontains=value).distinct('ship_to').order_by('ship_to')
            .values('pk')
        )
    )


def search_companies_by_bu(qs, _, value):
    if not value:
        return qs
    return qs.filter(business_unit__name__icontains=value)


def filter_export_pi_by_sold_to(qs, _, value):
    if not value:
        return qs
    qs = qs.select_related("sold_to").annotate(
        search_text=Concat(F('sold_to__sold_to_code'), Value(' - '), F('sold_to__sold_to_name'))).filter(
        search_text__icontains=value)
    return qs


class ExportPIFilter(MetadataFilterBase):
    code = django_filters.CharFilter(method=filter_export_pi_by_code)
    sold_to = django_filters.CharFilter(method=filter_export_pi_by_sold_to)

    class Meta:
        model = Contract
        fields = ["id"]


class ExportPIFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ExportPIFilter


class ExportSoldToFilter(MetadataFilterBase):
    search = django_filters.CharFilter(method=search_export_sold_to_by_code_or_name)

    class Meta:
        model = SoldToMaster
        fields = ["id"]


class ExportSoldToFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ExportSoldToFilter


class CartPiFilter(MetadataFilterBase):
    code = django_filters.CharFilter(method=filter_pi)

    class Meta:
        model = Contract
        fields = ["id"]


def filter_pi_no(qs, _, value):
    qs = qs.filter(
        Q(contract__code__exact=value)
    )
    return qs


def filter_eo_no(qs, _, value):
    qs = qs.filter(
        Q(eo_no__exact=value)
    )
    return qs


def filter_po_no(qs, _, value):
    qs = qs.filter(
        Q(po_no__exact=value)
    )
    return qs


def filter_sold_to(qs, _, value):
    qs = qs.annotate(
        search_text=Concat(F('contract__sold_to__sold_to_code'), Value(' - '),
                           F('contract__sold_to__sold_to_name'))).filter(
        Q(search_text__iexact=value) | Q(contract__sold_to__sold_to_code__iexact=value) | Q(
            contract__sold_to__sold_to_name__iexact=value))
    return qs


def filter_ship_to(qs, _, value):
    rs = value.replace("\n", "")
    pattern = "^%s - [\\s\\w,.]" % rs
    pattern_2 = "^\\d+ - %s$" % rs
    qs = qs.annotate(search_field=Replace('ship_to', Value('\n'), Value(''))).filter(
        Q(search_field__iexact=rs) | Q(search_field__iregex=fr"{pattern}") | Q(search_field__iregex=fr"{pattern_2}"))
    return qs


def filter_order_status(qs, _, value):
    query_objects = qs.none()
    if value:
        query_objects |= qs.filter(status__in=value)
    return qs & query_objects


def filter_order_status_sap(qs, _, value):
    query_objects = qs.none()
    if value:
        query_objects |= qs.filter(status_sap__in=value)
    return qs & query_objects


def filter_company(qs, _, value):
    qs = qs.filter(
        Q(sales_organization__code__exact=value)
    )
    return qs


def filter_bu(qs, _, value):
    qs = qs.filter(
        Q(sales_organization__business_unit__name__icontains=value)
    )
    return qs


def filter_last_update_range(qs, _, value):
    timezone_asia_bangkok = 7
    value = update_date_range_with_timezone(value, timezone_asia_bangkok)
    return filter_range_field(qs, "updated_at", value)


def filter_create_update_range(qs, _, value):
    timezone_asia_bangkok = 7
    value = update_date_range_with_timezone(value, timezone_asia_bangkok)
    return filter_range_field(qs, "created_at", value)


def filter_text(qs, _, value):
    sold_external_codes = sap_data_models.SoldToPartnerAddressMaster.objects.annotate(
        search_text=Concat(F('partner_code'), Value(' - '), F('name1'),
                           Value(' '), F('name2'),
                           Value(' '), F('name3'),
                           Value(' '), F('name4'))
    ).filter(search_text__icontains=value).values_list('sold_to_code', flat=True).distinct()

    qs = qs.filter(
        Q(sold_to__sold_to_code__in=sold_external_codes) | Q(contract__code__ilike=value)).distinct()
    return qs


class CartPiFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CartPiFilter


class CartFilter(MetadataFilterBase):
    input_search = django_filters.CharFilter(method=filter_text)

    class Meta:
        model = Contract
        fields = ["id"]


class CartFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CartFilter


class ExportShipToFilter(MetadataFilterBase):
    ship_to = django_filters.CharFilter(method=search_ship_to_by_input)

    class Meta:
        model = sap_migration_models.Order
        fields = ["ship_to"]


class ExportCompaniesFilter(MetadataFilterBase):
    search = django_filters.CharFilter(method=search_companies_by_bu)

    class Meta:
        model = SalesOrganization
        fields = ["business_unit"]


class ExportShipToFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ExportShipToFilter


class ExportCompaniesFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ExportCompaniesFilter


class ExportOrderFilter(MetadataFilterBase):
    pi_no = django_filters.CharFilter(method=filter_pi_no)
    eo_no = django_filters.CharFilter(method=filter_eo_no)
    po_no = django_filters.CharFilter(method=filter_po_no)
    sold_to = django_filters.CharFilter(method=filter_sold_to)
    ship_to = django_filters.CharFilter(method=filter_ship_to)
    status = ListObjectTypeFilter(input_class=ScgpExportOrderStatus, method=filter_order_status)
    status_sap = ListObjectTypeFilter(input_class=ScgpExportOrderStatusSAP, method=filter_order_status_sap)
    company = django_filters.CharFilter(method=filter_company)
    bu = django_filters.CharFilter(method=filter_bu)
    last_update = ObjectTypeFilter(
        input_class=DateRangeInput, method=filter_last_update_range
    )
    create_date = ObjectTypeFilter(
        input_class=DateRangeInput, method=filter_create_update_range
    )

    class Meta:
        model = sap_migration_models.Order
        fields = ["id"]


class ExportOrderFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ExportOrderFilter
