import django_filters
import graphene
from django.db.models import Value, Q, F
from django.db.models.functions import Concat

import sap_master_data.models
import sap_migration.models
from saleor.graphql.core.filters import ListObjectTypeFilter, MetadataFilterBase, ObjectTypeFilter
from saleor.graphql.core.types import FilterInputObjectType, SortInputObjectType, DateRangeInput
from saleor.graphql.utils.filters import filter_range_field
from scg_checkout.graphql.enums import SapOrderConfirmationStatus
from scg_checkout.graphql.helper import update_date_range_with_timezone
from scgp_customer import models


def filter_search_customer_contract(qs, _, value):
    return qs.filter(company_id__in=value)


class CustomerContractFilter(django_filters.FilterSet):
    company_ids = ListObjectTypeFilter(
        input_class=graphene.Int, method=filter_search_customer_contract
    )

    class Meta:
        model = models.CustomerContract
        fields = ["code"]


class CustomerContractFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CustomerContractFilter


class CustomerContractsSortField(graphene.Enum):
    CODE = ["code"]

    @property
    def description(self):
        if self.name in CustomerContractsSortField.__enum__._member_names_:
            sort_name = self.name.lower().replace("_", " ")
            return f"Sort contracts by {sort_name}."
        raise ValueError("Unsupported enum value: %s" % self.value)


class CustomerContractsSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = CustomerContractsSortField
        type_name = "contracts"


def search_company_by_bu(qs, _, value):
    if not value:
        return qs
    return qs.filter(business_unit__name__icontains=value)


class CustomerCompanyFilter(MetadataFilterBase):
    business_unit = django_filters.CharFilter(method=search_company_by_bu)

    class Meta:
        model = sap_migration.models.CompanyMaster
        fields = ["business_unit"]


class CustomerCompanyFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CustomerCompanyFilter


def search_sales_group_by_company(qs, _, value):
    if not value:
        return qs
    return qs.filter(company__name__icontains=value)


class CustomerSalesGroupFilter(MetadataFilterBase):
    company = django_filters.CharFilter(method=search_sales_group_by_company)

    class Meta:
        model = sap_migration.models.SalesGroupMaster
        fields = ["company"]


class CustomerSalesGroupFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CustomerSalesGroupFilter


def search_customer_material_code_name(qs, _, value):
    if not value:
        return qs
    return qs.annotate(search_text=Concat('code', Value(' - '), 'description_en')).filter(
        search_text__icontains=value).distinct()


class CustomerMaterialCodeNameFilter(MetadataFilterBase):
    material = django_filters.CharFilter(method=search_customer_material_code_name)

    class Meta:
        model = sap_migration.models.MaterialVariantMaster
        fields = ["id"]


class CustomerMaterialCodeNameFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CustomerMaterialCodeNameFilter


def filter_material_code_name(qs, _, value):
    order_line = sap_migration.models.OrderLines.objects.annotate(
        search_text=Concat('material_variant__code', Value(' - '), 'material_variant__name')
    ).filter(Q(search_text__icontains=value)
             | Q(material_variant__code__iexact=value)
             | Q(material_variant__name__iexact=value)).values_list('order_id', flat=True)
    qs = qs.filter(id__in=order_line)
    return qs


def filter_so_no(qs, _, value):
    qs = qs.filter(
        Q(so_no__exact=value)
    )
    return qs


def filter_contract_no(qs, _, value):
    qs = qs.filter(
        Q(contract__code__iexact=value)
    )
    return qs


def filter_dp_no(qs, _, value):
    qs = qs.filter(
        Q(dp_no__iexact=value)
    )
    return qs


def filter_invoice_no(qs, _, value):
    qs = qs.filter(
        Q(invoice_no__iexact=value)
    )
    return qs


def filter_bu(qs, _, value):
    qs = qs.filter(
        Q(company__business_unit__name__icontains=value)
    )
    return qs


def filter_company(qs, _, value):
    query_objects = qs.none()
    if value:
        query_objects |= qs.filter(company__code__icontains=value)
    return qs & query_objects


def filter_company_by_list(qs, _, value):
    query_objects = qs.none()
    if value:
        query_objects |= qs.filter(company__code__in=value)
    return qs & query_objects


def filter_po_no(qs, _, value):
    qs = qs.filter(
        Q(po_no__iexact=value)
    )
    return qs


def filter_sale_group(qs, _, value):
    qs = qs.filter(
        Q(sales_group__name__icontains=value)
    )
    return qs


def filter_last_update_range(qs, _, value):
    timezone_asia_bangkok = 7
    value = update_date_range_with_timezone(value, timezone_asia_bangkok)
    return filter_range_field(qs, "updated_at", value)


def filter_request_date_range(qs, _, value):
    timezone_asia_bangkok = 7
    value = update_date_range_with_timezone(value, timezone_asia_bangkok)
    return filter_range_field(qs, "request_date", value)


def filter_create_update_range(qs, _, value):
    timezone_asia_bangkok = 7
    value = update_date_range_with_timezone(value, timezone_asia_bangkok)
    return filter_range_field(qs, "created_at", value)


def filter_sold_to(qs, _, value):
    qs = qs.annotate(
        search_text=Concat(F('contract__sold_to__sold_to_code'), Value(' - '),
                           F('contract__sold_to__sold_to_name'))).filter(
        Q(search_text__iexact=value))
    return qs


def filter_distribution_channel(qs, _, value):
    if value:
        qs = qs.filter(distribution_channel__code=value)
    return qs


def filter_material_group(qs, _, value):
    list_value = []
    if value:
        for values in value:
            list_value.append(values.split(" -")[0])
        material_code = sap_master_data.models.MaterialSaleMaster.objects.filter(
            material_group1__in=list_value).values_list("material_code", flat=True).distinct()
        order_line = sap_migration.models.OrderLines.objects.filter(
            material_variant__code__in=material_code).values_list('order_id', flat=True)
        qs = qs.filter(id__in=order_line)
    return qs


def filter_order_confirmation_status(qs, _, value):
    if value:
        order_line = sap_migration.models.OrderLines.objects.filter(sap_confirm_status__in=value).values_list(
            'order_id',
            flat=True)
        qs = qs.filter(id__in=order_line)
    return qs


def filter_order_create_date(qs, _, value):
    if value:
        qs = qs.filter(
            Q(created_at__date=value)
        )
    return qs


class CustomerOrderFilter(MetadataFilterBase):
    sold_to = django_filters.CharFilter(method=filter_sold_to)
    material_code_name = django_filters.CharFilter(method=filter_material_code_name)
    so_no = django_filters.CharFilter(method=filter_so_no)
    contract_no = django_filters.CharFilter(method=filter_contract_no)
    dp_no = django_filters.CharFilter(method=filter_dp_no)
    invoice_no = django_filters.CharFilter(method=filter_invoice_no)
    bu = django_filters.CharFilter(method=filter_bu)
    company = django_filters.CharFilter(method=filter_company)
    sale_group = django_filters.CharFilter(method=filter_sale_group)
    create_date = ObjectTypeFilter(
        input_class=DateRangeInput, method=filter_create_update_range
    )
    # last_update = ObjectTypeFilter(
    #     input_class=DateRangeInput, method=filter_last_update_range
    # )

    request_delivery_date = ObjectTypeFilter(
        input_class=DateRangeInput, method=filter_request_date_range
    )

    class Meta:
        model = sap_migration.models.Order
        fields = ["id"]


class CustomerOrderFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CustomerOrderFilter


class CustomerOrderConfirmationFilter(MetadataFilterBase):
    sold_to = django_filters.CharFilter(method=filter_sold_to)
    company_name = ListObjectTypeFilter(input_class=graphene.String, method=filter_company_by_list)
    so_no = django_filters.CharFilter(method=filter_so_no)
    po_no = django_filters.CharFilter(method=filter_po_no)
    material = django_filters.CharFilter(method=filter_material_code_name)
    distribution_channel = django_filters.CharFilter(method=filter_distribution_channel)
    status = ListObjectTypeFilter(input_class=graphene.String, method=filter_order_confirmation_status)
    material_group = ListObjectTypeFilter(input_class=graphene.String, method=filter_material_group)
    order_create_date = django_filters.CharFilter(method=filter_order_create_date)

    class Meta:
        model = sap_migration.models.Order
        fields = ["id"]


class CustomerOrderConfirmationFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CustomerOrderConfirmationFilter
