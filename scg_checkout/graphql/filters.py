import django_filters
import graphene
from django.db.models import Q, Value, F, Subquery, OuterRef
from django.db.models.functions import Concat, Substr
import datetime
import sap_migration.models
from saleor.graphql.core.filters import MetadataFilterBase, EnumFilter
from saleor.graphql.core.filters import ListObjectTypeFilter, ObjectTypeFilter
from saleor.graphql.core.types import FilterInputObjectType, DateRangeInput
from saleor.graphql.utils.filters import filter_range_field
from sap_migration.graphql.enums import OrderType
from scg_checkout import models
from .enums import (
    ScgOrderStatus,
    ScgDomesticOrderStatusSAP,
    MaterialVariantType,
    SapOrderConfirmationStatus,
    AltMaterialType,
)
from sap_migration import models as migration_models
from sap_master_data import models as master_models
from .helper import update_date_range_with_timezone


def filter_search_contract(qs, _, value):
    if not value:
        return qs
    return qs.filter(company_id__in=value).distinct()


def filter_contract_by_grade_gram(qs, _, value):
    if not value:
        return qs
    qs = qs.filter(contractmaterial__material__material_code=value).distinct()
    return qs


def filter_contract_by_material_code(qs, _, value):
    if not value:
        return qs
    qs = qs.filter(contractmaterial__material__material_code=value).distinct()
    return qs


class TempContractFilter(django_filters.FilterSet):
    company_ids = ListObjectTypeFilter(
        input_class=graphene.Int, method=filter_search_contract
    )
    grade_gram = django_filters.CharFilter(method=filter_contract_by_grade_gram)
    material_code = django_filters.CharFilter(method=filter_contract_by_material_code)

    class Meta:
        model = migration_models.Contract
        fields = ["id"]


class TempContractFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = TempContractFilter


def filter_material(qs, _, value):
    if not value:
        return qs
    material_type = AltMaterialType.MATERIAL.value + AltMaterialType.GRADE_GRAM.value
    return qs.filter(material_code__icontains=value, material_type__in=material_type). \
        exclude(delete_flag="X")


class SuggestionMaterialFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method=filter_material)

    class Meta:
        model = master_models.MaterialMaster
        fields = ["search"]


class SuggestionMaterialFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = SuggestionMaterialFilter


def alter_material_filter_by_sold_to_code_name(qs, _, value):
    """
        search only by sold_to_code
    """
    if not value:
        return qs
    values = [x.strip(" ") for x in value.split("-")]
    return qs.filter(Q(alternate_material__sold_to__sold_to_code__iexact=values[0]))


def alter_material_filter_by_material_code(qs, _, value):
    qs = qs.filter(alternate_material__material_own__material_code__iexact=value)
    return qs


def alter_material_filter_by_grade(qs, _, value):
    """
        use grade [digit 4,5,6 ] of material code
    """
    material_class_codes = master_models.MaterialMaster.objects \
        .annotate(search_grade=Substr('material_code', 4, 3)) \
        .filter(search_grade__contains=value) \
        .values_list('material_code', flat=True).distinct()
    qs = qs.filter(Q(alternate_material__material_own__material_code__in=material_class_codes))
    return qs


def alter_material_filter_by_gram(qs, _, value):
    """
        use gram [digit 7,8,9 ] of material code
    """
    material_class_codes = master_models.MaterialMaster.objects \
        .annotate(search_gram=Substr('material_code', 7, 3)) \
        .filter(search_gram=value) \
        .values_list('material_code', flat=True).distinct()
    qs = qs.filter(Q(alternate_material__material_own__material_code__in=material_class_codes))
    return qs


class AlterMaterialFilter(django_filters.FilterSet):
    sold_to = django_filters.CharFilter(method=alter_material_filter_by_sold_to_code_name)
    material_code = django_filters.CharFilter(method=alter_material_filter_by_material_code)
    grade = django_filters.CharFilter(method=alter_material_filter_by_grade)
    gram = django_filters.CharFilter(method=alter_material_filter_by_gram)

    class Meta:
        model = migration_models.AlternateMaterialOs
        fields = ["sold_to"]


class AlterMaterialFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = AlterMaterialFilter


def search_temp_orders_by_status(qs, _, value):
    query_objects = qs.none()
    if value:
        query_objects |= qs.filter(status__in=value)
    return qs & query_objects


class TempOrderFilter(MetadataFilterBase):
    status = ListObjectTypeFilter(input_class=ScgOrderStatus, method=search_temp_orders_by_status)


class TempOrderFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = TempOrderFilter


def search_scg_sold_tos_by_code_or_name(qs, _, value):
    if not value:
        return qs
    return qs.annotate(search_text=Concat('sold_to_code', Value(' - '), 'sold_to_name')).filter(
        search_text__icontains=value)


class ScgSoldTosFilter(MetadataFilterBase):
    search = django_filters.CharFilter(method=search_scg_sold_tos_by_code_or_name)

    class Meta:
        model = migration_models.SoldToMaster
        fields = ["id"]


class ScgSoldTosFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ScgSoldTosFilter


def search_temp_product_by_material_code(qs, _, value):
    if not value:
        return qs
    return qs.filter(material_code__icontains=value, material_type="81")


def search_temp_product_by_grade_gram(qs, _, value):
    if not value:
        return qs
    return qs.filter(material_code__icontains=value, material_type="84")


def search_temp_product_by_grade_gram_code(qs, _, value):
    if not value:
        return qs
    regex = f"^.{'{3,8}'}({value}){'{1,6}'}.*$"
    return qs.filter(material_code__iregex=regex, material_type="84")


def search_material_master_by_material_code(qs, _, value):
    if not value:
        return qs
    return qs.filter(material_code__icontains=value, material_type__in=AltMaterialType.MATERIAL.value). \
        exclude(delete_flag="X")


def search_material_master_by_grade_gram(qs, _, value):
    if not value:
        return qs
    return qs.filter(material_code__icontains=value, material_type__in=AltMaterialType.GRADE_GRAM.value). \
        exclude(delete_flag="X")


def search_material_master_by_grade_gram_code(qs, _, value):
    if not value:
        return qs
    return qs.filter(material_code__icontains=value, material_type__in=AltMaterialType.GRADE_GRAM.value). \
        exclude(delete_flag="X")


class TempProductFilter(MetadataFilterBase):
    grade_gram = django_filters.CharFilter(method=search_material_master_by_grade_gram)
    material_code = django_filters.CharFilter(method=search_material_master_by_material_code)
    grade_gram_code = django_filters.CharFilter(method=search_material_master_by_grade_gram_code)

    class Meta:
        model = master_models.MaterialMaster
        fields = ["id"]


class TempProductFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = TempProductFilter


def search_material_by_material_code(qs, _, value):
    if not value:
        return qs
    return qs.filter(material_code__icontains=value, material_type__in=MaterialVariantType.MATERIAL.value). \
        exclude(delete_flag="X")


def search_material_by_grade_gram(qs, _, value):
    if not value:
        return qs
    return qs.filter(material_code__icontains=value, material_type=MaterialVariantType.GRADE_GRAM.value). \
        exclude(delete_flag="X")


def search_material_by_grade_gram_code(qs, _, value):
    if not value:
        return qs
    return qs.filter(material_code__icontains=value, material_type=MaterialVariantType.GRADE_GRAM.value). \
        exclude(delete_flag="X")


class MaterialMasterFilter(MetadataFilterBase):
    grade_gram = django_filters.CharFilter(method=search_material_by_grade_gram)
    material_code = django_filters.CharFilter(method=search_material_by_material_code)
    grade_gram_code = django_filters.CharFilter(method=search_material_by_grade_gram_code)

    class Meta:
        model = master_models.MaterialMaster
        fields = ["id"]


class MaterialMasterFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = MaterialMasterFilter


def filter_sale_organization_from_order(qs, _, value):
    qs = qs.filter(Q(order__sales_organization=value))
    return qs


def filter_create_by_from_order(qs, _, value):
    qs = qs.annotate(search_text=Concat('order__created_by__first_name', Value(' '),
                                        'order__created_by__last_name')).filter(
        Q(search_text__iexact=value))
    return qs


def filter_create_date_from_order(qs, _, value):
    lte_date = value.get('lte')
    if lte_date:
        lte_datetime = datetime.datetime.combine(lte_date, datetime.time.max)
        value['lte'] = lte_datetime

    return filter_range_field(qs, "order__created_at", value)


def filter_request_date_from_order_line(qs, _, value):
    return filter_range_field(qs, "order_line__request_date", value)


def filter_order_no_from_order(qs, _, value):
    qs = qs.filter(Q(order__order_no=value))
    return qs


def filter_so_no_from_order(qs, _, value):
    qs = qs.filter(Q(order__so_no=value))
    return qs


def filter_sold_to_from_order(qs, _, value):
    qs = qs.filter(Q(order__sold_to_id__in=value))
    return qs


def filter_po_no_from_order(qs, _, value):
    qs = qs.filter(Q(order__po_number=value))
    return qs


def filter_old_material_from_product(qs, _, value):
    qs = qs.filter(Q(old_product__material_code=value))
    return qs


def filter_old_grade_gram_from_product(qs, _, value):
    qs = qs.annotate(grade_gram=Substr('old_product__material_code', 1, 10)).filter(grade_gram=value)
    return qs


def filter_new_material_from_product(qs, _, value):
    qs = qs.filter(Q(new_product__material_code=value))
    return qs


def filter_new_grade_gram_from_product(qs, _, value):
    qs = qs.annotate(grade_gram=Substr('new_product__material_code', 1, 10)).filter(grade_gram=value)
    return qs


def filter_alternated_material_by_error_type(qs, _, value):
    rs = qs.filter(Q(error_type__iexact=value))
    if value == "all":
        rs = qs.filter(error_type__isnull=False)
    return rs


class AlternatedMaterialFilter(django_filters.FilterSet):
    sale_organization = django_filters.CharFilter(method=filter_sale_organization_from_order)
    create_by = django_filters.CharFilter(method=filter_create_by_from_order)
    order_no = django_filters.CharFilter(method=filter_order_no_from_order)
    so_no = django_filters.CharFilter(method=filter_so_no_from_order)
    po_no = django_filters.CharFilter(method=filter_po_no_from_order)
    old_material = django_filters.CharFilter(method=filter_old_material_from_product)
    old_grade_gram = django_filters.CharFilter(method=filter_old_grade_gram_from_product)
    new_material = django_filters.CharFilter(method=filter_new_material_from_product)
    new_grade_gram = django_filters.CharFilter(method=filter_new_grade_gram_from_product)
    created_date = ObjectTypeFilter(input_class=DateRangeInput, method=filter_create_date_from_order)
    request_date = ObjectTypeFilter(input_class=DateRangeInput, method=filter_request_date_from_order_line)
    sold_to = ListObjectTypeFilter(input_class=graphene.Int, method=filter_sold_to_from_order)
    error_type = django_filters.CharFilter(method=filter_alternated_material_by_error_type)

    class Meta:
        model = models.AlternatedMaterial
        fields = ["error_type"]


class AlternatedMaterialFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = AlternatedMaterialFilter


def filter_suggestion_create_by(qs, _, value):
    qs = qs.annotate(search_text=Concat('first_name', Value(' - '), 'last_name')).filter(
        Q(search_text__icontains=value))
    return qs


class SuggestionSearchUserByNameFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method=filter_suggestion_create_by)

    class Meta:
        model = models.User
        fields = ["search"]


class SuggestionSearchUserByNameFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = SuggestionSearchUserByNameFilter


def filter_order_draft_status(qs, _, value):
    return qs.filter(Q(status=value))


def filter_order_draft_type(qs, _, value):
    return qs.filter(type=value)


class OrderDraftFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(method=filter_order_draft_status)
    type = EnumFilter(input_class=OrderType, method=filter_order_draft_type)


class ScgOrderDraftFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = OrderDraftFilter


class OrderDraftsFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = OrderDraftFilter


def search_domestic_sold_to(qs, _, value):
    if not value:
        return qs
    return qs.annotate(search_text=Concat('sold_to_code', Value(' - '), 'sold_to_name')).filter(
        search_text__icontains=value)


def search_domestic_sold_tos_by_code_or_name(qs, _, value):
    all_data = qs.annotate(
        name=Subquery(
            master_models.SoldToPartnerAddressMaster.objects.filter(
                partner_code=OuterRef('sold_to_code'),
            ).distinct("partner_code").annotate(
                new_name=Concat(F('name1'), Value(' '), F('name2'), Value(' '), F('name3'),
                                Value(' '), F('name4'))).values('new_name')[:1])) \
        .annotate(full_name=Concat(F("sold_to_code"), Value(' - '), F('name')))
    qs = all_data.filter(full_name__icontains=value).distinct()
    return qs


class DomesticSoldToFilter(MetadataFilterBase):
    sold_to = django_filters.CharFilter(method=search_domestic_sold_to)
    search = django_filters.CharFilter(method=search_domestic_sold_tos_by_code_or_name)

    class Meta:
        model = master_models.SoldToMaster
        fields = ["id"]


class DomesticSoldToFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = DomesticSoldToFilter


def search_domestic_material_code_name(qs, _, value):
    if not value:
        return qs
    return qs.annotate(search_text=Concat('code', Value(' - '), 'name', Value(' - '), 'description_en')).filter(
        search_text__icontains=value)


class DomesticMaterialCodeNameFilter(MetadataFilterBase):
    material = django_filters.CharFilter(method=search_domestic_material_code_name)

    class Meta:
        model = migration_models.MaterialVariantMaster
        fields = ["id"]


class DomesticMaterialCodeNameFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = DomesticMaterialCodeNameFilter


def search_domestic_sales_employee(qs, _, value):
    if not value:
        return qs
    return qs.annotate(search_text=Concat('code', Value(' - '), 'name')).filter(
        search_text__icontains=value)


class DomesticSaleEmployeeFilter(MetadataFilterBase):
    sales_employeee = django_filters.CharFilter(method=search_domestic_sales_employee)

    class Meta:
        model = migration_models.SalesEmployee
        fields = ["id"]


class DomesticSaleEmployeeFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = DomesticSaleEmployeeFilter


def search_company_by_bu(qs, _, value):
    if not value:
        return qs
    return qs.filter(business_unit__name__icontains=value)


class DomesticCompanyFilter(MetadataFilterBase):
    business_unit = django_filters.CharFilter(method=search_company_by_bu)

    class Meta:
        model = master_models.CompanyMaster
        fields = ["business_unit"]


class DomesticCompanyFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = DomesticCompanyFilter


def search_sales_group_by_company(qs, _, value):
    if not value:
        return qs
    return qs.filter(company__code__icontains=value)


class DomesticSalesGroupFilter(MetadataFilterBase):
    company = django_filters.CharFilter(method=search_sales_group_by_company)

    class Meta:
        model = migration_models.SalesGroupMaster
        fields = ["company"]


class DomesticSalesGroupFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = DomesticSalesGroupFilter


def filter_sold_to(qs, _, value):
    qs = qs.annotate(
        search_text=Concat(F('sold_to__sold_to_code'), Value(' - '), F('sold_to__sold_to_name'))).filter(
        Q(search_text__iexact=value) | Q(sold_to__sold_to_code__iexact=value) | Q(sold_to__sold_to_name__iexact=value))
    return qs


def filter_sold_to_order_confirmation(qs, _, value):
    qs = qs.annotate(
        search_text=Concat(F('contract__sold_to__sold_to_code'), Value(' - '),
                           F('contract__sold_to__sold_to_name'))).filter(
        Q(search_text__in=value)
    )

    return qs


def filter_contract_no(qs, _, value):
    qs = qs.filter(
        Q(contract__code__iexact=value)
    )
    return qs


def filter_material_code_name(qs, _, value):
    if value:
        order_line = migration_models.OrderLines.objects.annotate(
            search_text=Concat('material_variant__code', Value(' - '), 'material_variant__name')
        ).filter(Q(search_text__icontains=value)
                 | Q(material_variant__code__iexact=value)
                 | Q(material_variant__name__iexact=value)).values_list('order_id', flat=True)
        qs = qs.filter(id__in=order_line)
    return qs


def filter_material_code_name_for_order_confirmation(qs, _, value):
    order_line = migration_models.OrderLines.objects.annotate(
        search_text=Concat('material_variant__code', Value(' - '), 'material_variant__description_en')
    ).filter(Q(search_text__in=value)).values_list('order_id', flat=True)
    qs = qs.filter(id__in=order_line)
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


def filter_sale_org_by_list(qs, _, value):
    query_objects = qs.none()
    if value:
        query_objects |= qs.filter(sales_organization_id__code__in=value)
    return qs & query_objects


def filter_sale_group(qs, _, value):
    qs = qs.filter(
        Q(sales_group__code=value)
    )
    return qs


def filter_sale_employee(qs, _, value):
    if value:
        qs = qs.annotate(search_text=Concat('scgp_sales_employee__code', Value(' - '),
                                            'scgp_sales_employee__name')).filter(
            Q(search_text__iexact=value)
            | Q(scgp_sales_employee__code__iexact=value)
            | Q(scgp_sales_employee__name__iexact=value)
        )
    return qs


def filter_so_no(qs, _, value):
    if value:
        qs = qs.filter(
            Q(so_no__iexact=value)
        )
    return qs


def filter_po_no(qs, _, value):
    if value:
        qs = qs.filter(
            Q(po_no__iexact=value)
        )
    return qs


def filter_order_type(qs, _, value):
    qs = qs.filter(
        Q(order_type__iexact=value)
    )
    return qs


def filter_order_status_sap(qs, _, value):
    query_objects = qs.none()
    if value:
        query_objects |= qs.filter(status_sap__in=value)
    return qs & query_objects


def filter_last_update_range(qs, _, value):
    timezone_asia_bangkok = 7
    value = update_date_range_with_timezone(value, timezone_asia_bangkok)
    return filter_range_field(qs, "updated_at", value)


def filter_create_update_range(qs, _, value):
    timezone_asia_bangkok = 7
    value = update_date_range_with_timezone(value, timezone_asia_bangkok)
    return filter_range_field(qs, "created_at", value)


def filter_order_confirmation_status(qs, _, value):
    if value:
        order_line = migration_models.OrderLines.objects.filter(sap_confirm_status__in=value).values_list('order_id',
                                                                                                          flat=True)
        qs = qs.filter(id__in=order_line)
    return qs


def filter_order_create_date(qs, _, value):
    return filter_range_field(qs, "created_at__date", value)


def filter_material_group(qs, _, value):
    list_value = []
    if value:
        for values in value:
            list_value.append(values.split(" -")[0])
        material_code = master_models.MaterialSaleMaster.objects.filter(material_group1__in=list_value).values_list(
            "material_code", flat=True).distinct()
        order_line = migration_models.OrderLines.objects.filter(
            material_variant__code__in=material_code).values_list('order_id', flat=True)
        qs = qs.filter(id__in=order_line)
    return qs


def filter_distribution_channel(qs, _, value):
    if value:
        qs = qs.filter(distribution_channel__code=value)
    return qs


class DomesticOrderFilter(MetadataFilterBase):
    sold_to = django_filters.CharFilter(method=filter_sold_to)
    material_code_name = django_filters.CharFilter(method=filter_material_code_name)
    so_no = django_filters.CharFilter(method=filter_so_no)
    contract_no = django_filters.CharFilter(method=filter_contract_no)
    dp_no = django_filters.CharFilter(method=filter_dp_no)
    invoice_no = django_filters.CharFilter(method=filter_invoice_no)
    bu = django_filters.CharFilter(method=filter_bu)
    company = django_filters.CharFilter(method=filter_company)
    sale_group = django_filters.CharFilter(method=filter_sale_group)
    sale_employee = django_filters.CharFilter(method=filter_sale_employee)
    order_type = django_filters.CharFilter(method=filter_order_type)
    status_sap = ListObjectTypeFilter(input_class=ScgDomesticOrderStatusSAP, method=filter_order_status_sap)
    create_date = ObjectTypeFilter(
        input_class=DateRangeInput, method=filter_create_update_range
    )
    last_update = ObjectTypeFilter(
        input_class=DateRangeInput, method=filter_last_update_range
    )

    class Meta:
        model = sap_migration.models.Order
        fields = ["id"]


class DomesticOrderFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = DomesticOrderFilter


class DomesticOrderConfirmationFilter(MetadataFilterBase):
    sold_to = ListObjectTypeFilter(input_class=graphene.String, method=filter_sold_to_order_confirmation)
    sale_organization = ListObjectTypeFilter(input_class=graphene.String, method=filter_sale_org_by_list)
    so_no = django_filters.CharFilter(method=filter_so_no)
    po_no = django_filters.CharFilter(method=filter_po_no)
    material = ListObjectTypeFilter(input_class=graphene.String,
                                    method=filter_material_code_name_for_order_confirmation)
    distribution_channel = django_filters.CharFilter(method=filter_distribution_channel)
    status = ListObjectTypeFilter(input_class=graphene.String, method=filter_order_confirmation_status)
    material_group = ListObjectTypeFilter(input_class=graphene.String, method=filter_material_group)
    order_create_date = ObjectTypeFilter(input_class=DateRangeInput, method=filter_order_create_date)
    bu = django_filters.CharFilter()

    class Meta:
        model = sap_migration.models.Order
        fields = ["so_no"]


class DomesticOrderConfirmationFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = DomesticOrderConfirmationFilter


def filter_route_by_code(qs, _, value):
    if value:
        qs = qs.filter(route_code__icontains=value)
    return qs


def filter_route_by_name(qs, _, value):
    if value:
        qs = qs.filter(route_description__icontains=value)
    return qs


class RouteFilter(django_filters.FilterSet):
    route_code = django_filters.CharFilter(method=filter_route_by_code)
    route_description = django_filters.CharFilter(method=filter_route_by_name)

    class Meta:
        model = migration_models.Route
        fields = ["route_code", "route_description"]


class RouteFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RouteFilter


def search_material_code_description_en(qs, _, value):
    return qs.annotate(search_text=Concat('code', Value(' - '), 'description_en')).filter(
        search_text__icontains=value)


class MaterialCodeDescriptionFilter(MetadataFilterBase):
    material = django_filters.CharFilter(method=search_material_code_description_en)

    class Meta:
        model = migration_models.MaterialVariantMaster
        fields = ["id"]


class MaterialCodeDescriptionFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = MaterialCodeDescriptionFilter


def suggestion_search_code_name_sold_to_partner_address_master(qs, _, value):
    if not value:
        return qs
    return qs.annotate(search_text=Concat(
        'partner_code',
        Value('-'),
        'name1',
        Value(' '),
        'name2',
        Value(' '),
        'name3',
        Value(' '),
        'name4'
    )).filter(
        search_text__icontains=value)


class ChangeOrderShipToFilter(MetadataFilterBase):
    search = django_filters.CharFilter(method=suggestion_search_code_name_sold_to_partner_address_master)

    class Meta:
        model = master_models.SoldToPartnerAddressMaster
        fields = ["id"]


class ChangeOrderShipToFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ChangeOrderShipToFilter


class ChangeOrderSoldToFilter(MetadataFilterBase):
    search = django_filters.CharFilter(method=suggestion_search_code_name_sold_to_partner_address_master)

    class Meta:
        model = master_models.SoldToPartnerAddressMaster
        fields = ["id"]


class ChangeOrderSoldToFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ChangeOrderSoldToFilter


def search_pending_order_report_ship_tos(qs, _, value):
    if not value:
        return qs
    address_code_list = master_models.SoldToChannelPartnerMaster.objects.filter(partner_code__icontains=value,
                                                                                partner_role="WE",
                                                                                distribution_channel_code__in=["10",
                                                                                                               "20"]).distinct(
        "address_link").values(
        "address_link")
    qs = qs.filter(address_code__in=address_code_list, partner_code__isnull=False)
    return qs


class PendingOrderReportShipTosFilter(MetadataFilterBase):
    search = django_filters.CharFilter(method=search_pending_order_report_ship_tos)

    class Meta:
        model = master_models.SoldToPartnerAddressMaster
        fields = ["id"]


class PendingOrderReportShipTosFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = PendingOrderReportShipTosFilter
