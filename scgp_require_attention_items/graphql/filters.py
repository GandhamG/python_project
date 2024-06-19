import django_filters
import graphene
from django.db.models import (
    Q,
    Value,
    F,
    Subquery
)

import operator
from functools import reduce
from django.db.models.functions import Concat
from graphene import InputObjectType

from saleor.graphql.core.filters import (
    MetadataFilterBase,
    ListObjectTypeFilter,
    ObjectTypeFilter,
    EnumFilter,
)
from saleor.graphql.core.types import (
    FilterInputObjectType,
    DateRangeInput
)
from scg_checkout.graphql.helper import update_date_range_with_timezone
from scgp_export.graphql.enums import ScgpExportOrderStatus
from scgp_require_attention_items.graphql.enums import (
    ScgpRequireAttentionTypeData,
    ScgpRequireAttentionItemStatus,
    DeliveryBlock09Enum,
    SaleOrderStatusEnum,
    MaterialPricingGroupEnum
)
from sap_master_data import models as sap_master_data_models
from sap_migration import models as sap_migrations_models
from scgp_require_attention_items.graphql.sorters import SalesOrderSortingInput


def search_require_attention_sold_to(qs, _, value):
    if not value:
        return qs
    return qs.annotate(search_text=Concat('sold_to_code', Value(' - '), 'sold_to_name')).filter(
        search_text__icontains=value)


def search_require_attention_ship_to(qs, _, value):
    if not value:
        return qs
    return qs.filter(pk__in=Subquery(
        sap_migrations_models.OrderLines.objects.filter(ship_to__icontains=value).distinct('ship_to').values('pk')
    ))


def search_require_attention_sale_employee(qs, _, value):
    if not value:
        return qs
    return qs.filter(pk__in=Subquery(
        sap_migrations_models.Order.objects.filter(sales_employee__icontains=value).distinct('sales_employee').values(
            'pk')
    ))


def search_require_attention_material(qs, _, value):
    if not value:
        return qs
    return qs.annotate(
        search_text=Concat('material_code', Value(' - '), 'description_en')
    ).filter(search_text__icontains=value)


def search_require_attention_material_grade_gram(qs, _, value):
    if not value:
        return qs
    return qs.annotate(search_text=Concat('grade', Value(' '),
                                          'basis_weight')).filter(
        search_text__icontains=value)


def search_sales_organization_by_bu(qs, _, value):
    if not value:
        return qs
    return qs.filter(business_unit__name__icontains=value)


def search_sales_group_by_sales_organization(qs, _, value):
    if not value:
        return qs
    return qs.filter(sales_organization__name__icontains=value)


def search_require_attention_plant(qs, _, value):
    if not value:
        return qs
    return qs.filter(plant__icontains=value)


def filter_sold_to(qs, _, value):
    if value:
        sold_to_codes = sap_master_data_models.SoldToMaster.objects.annotate(
            search_text=Concat('sold_to_code', Value(' - '), 'sold_to_name')
        ).filter(search_text__icontains=value).values_list('sold_to_code', flat=True).distinct()
        qs = qs.filter(order__contract__sold_to__sold_to_code__in=sold_to_codes)
    return qs


def filter_ship_to(qs, _, value):
    qs = qs.filter(ship_to__iexact=value)
    return qs


def filter_po_no(qs, _, value):
    qs = qs.filter(
        Q(order__po_no__iexact=value)
    )
    return qs


def filter_sale_employee(qs, _, value):
    value = value.split(" -")
    qs = qs.filter(
        Q(order__sales_employee__iexact=value[0])
    )
    return qs


def filter_sale_organization(qs, _, value):
    qs = qs.filter(
        Q(order__sales_organization__name__icontains=value)
    )
    return qs


def filter_bu(qs, _, value):
    qs = qs.filter(
        Q(order__sales_organization__business_unit__name__icontains=value)
    )
    return qs


def filter_sale_group(qs, _, value):
    qs = qs.filter(
        Q(order__sales_organization__salesgroupmaster__name__icontains=value)
    )
    return qs


def filter_attention_type(qs, _, value):
    if value:
        qs = qs.filter(attention_type__icontains=value[0])
    return qs


def filter_order_status(qs, _, value):
    if not value:
        return qs
    return qs.filter(order__status__iexact=ScgpExportOrderStatus[str(value)].value)


def filter_item_status(qs, _, value):
    if not value:
        return qs
    return qs.filter(item_status_en__iexact=ScgpRequireAttentionItemStatus[str(value)].value)


def filter_material(qs, _, value):
    if value:
        query = reduce(
            operator.or_,
            (Q(material_variant__code__iexact=line) for line in value),
        )
        return qs.filter(query)
    else:
        return qs


def filter_material_grade_gram(qs, _, value):
    if value:
        query = reduce(
            operator.or_,
            (Q(material_variant__code__icontains=line) for line in value),
        )
        qs = qs.filter(query)
    return qs


def filter_material_group(qs, _, value):
    material = sap_master_data_models.MaterialSaleMaster.objects.filter(material_group1=value).values_list(
        'material_code', flat=True)
    qs = qs.filter(
        Q(contract_material__material_code__in=material)
    )
    return qs


def filter_plant(qs, _, value):
    if value:
        qs = qs.filter(
            Q(plant__in=value)
        )
        return qs


def filter_request_date(qs, _, value):
    qs = qs.filter(
        Q(request_date=value)
    )
    return qs


def filter_confirm_date(qs, _, value):
    qs = qs.filter(
        Q(confirmed_date=value)
    )
    return qs


class RequireAttentionSalesOrganizationFilter(MetadataFilterBase):
    business_unit = django_filters.CharFilter(method=search_sales_organization_by_bu)

    class Meta:
        model = sap_master_data_models.SalesOrganizationMaster
        fields = ["business_unit"]


class RequireAttentionSalesGroupFilter(MetadataFilterBase):
    sales_organization = django_filters.CharFilter(method=search_sales_group_by_sales_organization)

    class Meta:
        model = sap_migrations_models.SalesGroupMaster
        fields = ["sales_organization"]


class RequireAttentionSalesOrganizationFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RequireAttentionSalesOrganizationFilter


class RequireAttentionSalesGroupFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RequireAttentionSalesGroupFilter


class RequireAttentionSoldToFilter(MetadataFilterBase):
    sold_to = django_filters.CharFilter(method=search_require_attention_sold_to)

    class Meta:
        model = sap_master_data_models.SoldToMaster
        fields = ["id"]


class RequireAttentionSoldToFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RequireAttentionSoldToFilter


class RequireAttentionShipToFilter(MetadataFilterBase):
    ship_to = django_filters.CharFilter(method=search_require_attention_ship_to)

    class Meta:
        model = sap_migrations_models.OrderLines
        fields = ["ship_to"]


class RequireAttentionShipToFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RequireAttentionShipToFilter


class RequireAttentionSaleEmployeeFilter(MetadataFilterBase):
    sale_employee = django_filters.CharFilter(method=search_require_attention_sale_employee)

    class Meta:
        model = sap_migrations_models.Order
        fields = ["id"]


class RequireAttentionSaleEmployeeFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RequireAttentionSaleEmployeeFilter


class RequireAttentionMaterialFilter(MetadataFilterBase):
    material = django_filters.CharFilter(method=search_require_attention_material)

    class Meta:
        model = sap_master_data_models.MaterialMaster
        fields = ["id"]


class RequireAttentionMaterialFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RequireAttentionMaterialFilter


class RequireAttentionPlantFilter(MetadataFilterBase):
    plant = django_filters.CharFilter(method=search_require_attention_plant)

    class Meta:
        model = sap_migrations_models.OrderLines
        fields = ["plant"]


class RequireAttentionPlantFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RequireAttentionPlantFilter


class RequireAttentionItemsFilter(MetadataFilterBase):
    sold_to = django_filters.CharFilter(method=filter_sold_to)
    ship_to = django_filters.CharFilter(method=filter_ship_to)
    po_no = django_filters.CharFilter(method=filter_po_no)
    bu = django_filters.CharFilter(method=filter_bu)
    sale_organization = django_filters.CharFilter(method=filter_sale_organization)
    sale_group = django_filters.CharFilter(method=filter_sale_group)
    sale_employee = django_filters.CharFilter(method=filter_sale_employee)
    material = ListObjectTypeFilter(input_class=graphene.String, method=filter_material)
    material_grade_gram = ListObjectTypeFilter(input_class=graphene.String, method=filter_material_grade_gram)
    material_group = django_filters.CharFilter(method=filter_material_group)
    plant = ListObjectTypeFilter(input_class=graphene.String, method=filter_plant)
    attention_type = ListObjectTypeFilter(input_class=ScgpRequireAttentionTypeData, method=filter_attention_type)
    order_status = django_filters.CharFilter(method=filter_order_status)
    item_status = django_filters.CharFilter(method=filter_item_status)
    request_date = django_filters.CharFilter(method=filter_request_date)
    confirm_date = django_filters.CharFilter(method=filter_confirm_date)
    overdue_1 = django_filters.BooleanFilter()
    overdue_2 = django_filters.BooleanFilter()

    class Meta:
        model = sap_migrations_models.OrderLines
        fields = ["id", ]


class RequireAttentionItemsFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RequireAttentionItemsFilter


class RequireAttentionMaterialGradeGramFilter(MetadataFilterBase):
    material_grade_gram = django_filters.CharFilter(method=search_require_attention_material_grade_gram)

    class Meta:
        model = sap_master_data_models.MaterialClassificationMaster
        fields = ["id"]


class RequireAttentionMaterialGradeGramFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RequireAttentionMaterialGradeGramFilter


def filter_sales_order_by_sale_org(qs, _, value):
    if value and value != 'All':
        qs = qs.filter(
            Q(order__sales_organization__code__iexact=value)
        )
    return qs


def filter_sale_order_by_sale_group(qs, _, value):
    if value == 'All':
        list_code = sap_migrations_models.SalesGroupMaster.objects.all().values('code')
        value = []
        for code in list_code:
            value.append(code['code'])
    else:
        value = [value]
    return qs.filter(order__sales_group__code__in=value)


def filter_sale_order_by_order_type(qs, _, value):
    if value == 'All':
        return qs.filter(order__order_type__in=['ZOR', 'ZBV'])
    if value:
        qs = qs.filter(order__order_type__iexact=value)
    return qs


def filter_sale_order_by_channel(qs, _, value):
    if value == 'All':
        value = ['10', '20']
    else:
        value = [value]
    qs = qs.filter(order__distribution_channel__code__in=value)
    return qs


def filter_range_field_sale_order(qs, field, value):
    gte, lte = value.get("gte"), value.get("lte")
    if gte:
        lookup = {f"order__{field}__gte": gte}
        qs = qs.filter(**lookup)
    if lte:
        lookup = {f"order__{field}__lte": lte}
        qs = qs.filter(**lookup)
    return qs


def filter_sale_order_by_create_date_range(qs, _, value):
    timezone_asia_bangkok = 7
    value = update_date_range_with_timezone(value, timezone_asia_bangkok)
    return filter_range_field_sale_order(qs, "created_at", value)


def filter_sale_order_by_request_delivery_date_range(qs, _, value):
    timezone_asia_bangkok = 7
    value = update_date_range_with_timezone(value, timezone_asia_bangkok)
    return filter_range_field_sale_order(qs, "request_delivery_date", value)


def filter_sale_order_by_sold_to(qs, _, value):
    if value:
        return qs.filter(order__contract__sold_to__sold_to_code__in=value[0])
    return qs


def filter_sale_order_no_by_sale_order(qs, _, value):
    if value:
        qs = qs.filter(order__so_no__iexact=value)
    return qs


def filter_sale_order_by_purchase_order_no(qs, _, value):
    if value:
        qs = qs.filter(purch_nos__iexact=value)
    return qs


def filter_sale_order_by_sales_employee_no(qs, _, value):
    if value:
        qs = qs.select_related("order__scgp_sales_employee").annotate(
            search_text=Concat(F('order__scgp_sales_employee__code'), Value(' - '),
                               F('order__scgp_sales_employee__name'))).filter(
            Q(search_text__iexact=value) | Q(order__scgp_sales_employee__code__iexact=value) | Q(
                order__scgp_sales_employee__name__iexact=value))
    return qs


def filter_material_pricing_group(qs, _, value):
    if value:
        qs = qs.filter(material_pricing_group__iexact=MaterialPricingGroupEnum.get(value).value)
    return qs


def filter_sale_order_by_plant(qs, _, value):
    if value:
        qs = qs.filter(plant__iexact=value)
    return qs


def get_material_code(record):
    try:
        return record.material_variant.code
    except:
        return None


def clean_list_material(list_material):
    seen = set(list_material)
    if None in seen:
        seen.remove(None)
    return list(seen)


def filter_material_group_1(qs, _, value):
    if not value[0][0]:
        return qs
    if value[1][0] == 'All':
        distribution_channel_code = ['10', '20']
    else:
        distribution_channel_code = [value[1][0]]
    if value[2][0] == 'All':
        list_code = sap_master_data_models.SalesOrganizationMaster.objects.all().values('code')
        sales_organization_code = []
        for code in list_code:
            sales_organization_code.append(code.get('code'))
    else:
        sales_organization_code = [value[2][0]]
    if qs:
        list_material_code = [get_material_code(record) for record in qs]
        list_material_code = clean_list_material(list_material_code)
    else:
        return qs.none()
    if value:
        list_material = sap_master_data_models.MaterialSaleMaster.objects.filter(
            material_group1__iexact=str(value[0][0]),
            distribution_channel_code__in=distribution_channel_code,
            sales_organization_code__in=sales_organization_code,
            material_code__in=list_material_code
        ).values_list('material_code', flat=True)
        if list_material:
            return qs.filter(
                material_variant__material__material_code__in=list(list_material))
        else:
            return qs.none()
    return qs


def filter_sale_order_by_delivery_block(qs, _, value):
    if value:
        qs = qs.filter(order__delivery_block__iexact=DeliveryBlock09Enum.get(value).value)
    return qs


def filter_sale_order_by_create_by(qs, _, value):
    if value:
        qs = qs.filter(order__created_by__id=int(value))
    return qs


def filter_sale_order_by_status(qs, _, value):
    if value and value != 'All':
        return qs.filter(order__status__iexact=value)
    return qs.filter(order__status__in=["Pending", "Complete"])


def filter_sale_order_by_require_attention_flag(qs, _, value):
    if value and value != 'All':
        qs = qs.filter(attention_type__icontains=ScgpRequireAttentionTypeData.get(value).value)
    return qs


def filter_material_no_material_description(qs, _, value):
    if value:
        query = reduce(
            operator.or_,
            (Q(search_text__iexact=line) for line in value),
        )
        qs = qs.annotate(
            search_text=Concat('material_variant__code', Value(' - '), 'material_variant__description_en')
        ).filter(query)
    return qs


def validate_input_sale_order_grade_gram(grade_gram_input):
    grade_gram_input = grade_gram_input.replace(" ", "")
    if grade_gram_input.count("-") > 1:
        raise ValueError("Invalid input for grade gram")
    if '-' in grade_gram_input:
        return grade_gram_input.split('-')
    return [grade_gram_input, grade_gram_input]


def filter_sale_order_by_material_grade_gram(qs, _, value):
    if value:
        qs = qs.filter(material_variant__code__icontains=value)
    return qs


class SalesOrderFilter(MetadataFilterBase):
    sale_org = django_filters.CharFilter(method=filter_sales_order_by_sale_org)
    channel = django_filters.CharFilter(method=filter_sale_order_by_channel)
    order_type = django_filters.CharFilter(method=filter_sale_order_by_order_type)
    sale_group = django_filters.CharFilter(method=filter_sale_order_by_sale_group)
    sold_to = ListObjectTypeFilter(
        input_class=graphene.List(graphene.String),
        method=filter_sale_order_by_sold_to,
        required=True
    )
    create_date = ObjectTypeFilter(
        input_class=DateRangeInput, method=filter_sale_order_by_create_date_range
    )
    request_delivery_date = ObjectTypeFilter(
        input_class=DateRangeInput, method=filter_sale_order_by_request_delivery_date_range
    )
    sale_order_no = django_filters.CharFilter(method=filter_sale_order_no_by_sale_order)
    purchase_order_no = django_filters.CharFilter(method=filter_sale_order_by_purchase_order_no)
    sales_employee_no = django_filters.CharFilter(method=filter_sale_order_by_sales_employee_no)
    material_no_material_description = ListObjectTypeFilter(input_class=graphene.String,
                                                            method=filter_material_no_material_description)
    material_pricing_group = EnumFilter(input_class=MaterialPricingGroupEnum, method=filter_material_pricing_group)
    plant = django_filters.CharFilter(method=filter_sale_order_by_plant)
    material_group_1 = ListObjectTypeFilter(input_class=graphene.List(graphene.String),
                                            method=filter_material_group_1)
    delivery_block = EnumFilter(input_class=DeliveryBlock09Enum, method=filter_sale_order_by_delivery_block)
    create_by = django_filters.CharFilter(method=filter_sale_order_by_create_by)
    status = EnumFilter(input_class=SaleOrderStatusEnum, method=filter_sale_order_by_status)
    require_attention_flag = EnumFilter(input_class=ScgpRequireAttentionTypeData,
                                        method=filter_sale_order_by_require_attention_flag)

    class Meta:
        model = sap_migrations_models.OrderLines
        fields = ["id", ]


class SalesOrderFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = SalesOrderFilter


class InputSalesOrder(InputObjectType):
    sold_to_id = graphene.Argument(graphene.ID, required=True)
    direction = SalesOrderSortingInput(required=True)


def suggestion_search_material_grade_gram(qs, _, value):
    if value:
        return qs.annotate(search_text=Concat('code', Value(' - '), 'description_en')).filter(
            search_text__icontains=value)
    return qs


def suggestion_search_code_slash_grade_gram(qs, _, value):
    if value:
        return qs.annotate(search_text=Concat('code', Value(' / '), 'description_en')).filter(
            search_text__icontains=value)
    return qs


class SuggestionSearchMaterialGradeGramFilter(MetadataFilterBase):
    input = django_filters.CharFilter(method=suggestion_search_material_grade_gram)
    material_on_hand = django_filters.CharFilter(method=suggestion_search_code_slash_grade_gram)


class SuggestionSearchMaterialGradeGramFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = SuggestionSearchMaterialGradeGramFilter


class ReportOrderPendingSoldToFilter(MetadataFilterBase):
    sold_to = django_filters.CharFilter(method=search_require_attention_sold_to)

    class Meta:
        model = sap_master_data_models.SoldToMaster
        fields = ["id"]


class ReportOrderPendingSoldToFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ReportOrderPendingSoldToFilter


def suggestion_search_material_grade_gram_report_order_pending(qs, _, value):
    if value:
        return qs.annotate(search_text=Concat('code', Value(' - '), 'description_th')).filter(
            search_text__icontains=value)
    return qs


class SuggestionSearchMaterialGradeGramFilterReportOrderPending(MetadataFilterBase):
    input = django_filters.CharFilter(method=suggestion_search_material_grade_gram_report_order_pending)


class SuggestionSearchMaterialGradeGramFilterInputReportOrderPending(FilterInputObjectType):
    class Meta:
        filterset_class = SuggestionSearchMaterialGradeGramFilterReportOrderPending
