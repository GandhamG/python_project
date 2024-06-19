import django_filters
import graphene
from django.db.models import Q
from django.db.models import Value
from django.db.models.functions import Concat

import sap_migration.models
from saleor.graphql.core.filters import ObjectTypeFilter, MetadataFilterBase, ListObjectTypeFilter
from saleor.graphql.core.types import FilterInputObjectType, DateRangeInput
from saleor.graphql.utils.filters import filter_range_field
from saleor.account.models import User

from sap_master_data import models as sap_data_models


def filter_employee_id_scgp_user(qs, _, value):
    qs = qs.filter(
        Q(scgp_user__employee_id__iexact=value) | Q(scgp_user__username__iexact=value) | Q(
            scgp_user__ad_user__iexact=value),
    )
    return qs


def filter_last_name_scgp_user(qs, _, value):
    qs = qs.filter(
        Q(last_name__icontains=value),
    )
    return qs


def filter_first_name_scgp_user(qs, _, value):
    qs = qs.filter(
        Q(first_name__icontains=value),
    )
    return qs


def filter_email_scgp_user(qs, _, value):
    qs = qs.filter(
        Q(email__iexact=value),
    )
    return qs


def filter_parent_group_scgp_user(qs, _, value):
    qs = qs.filter(
        Q(scgp_user__user_parent_group__id=value),
    )
    return qs


def filter_group_scgp_user(qs, _, value):
    qs = qs.filter(
        Q(groups__id=value),
    )
    return qs


def filter_updated_by_scgp_user(qs, _, value):
    qs = qs.annotate(
        search_text=Concat('scgp_user__updated_by__first_name', Value(' '), 'scgp_user__updated_by__last_name')).filter(
        search_text__icontains=value)
    return qs


def filter_status_scgp_user(qs, _, value):
    qs = qs.filter(
        Q(is_active=value),
    )
    return qs


def filter_bu_scgp_user(qs, _, value):
    qs = qs.filter(
        Q(scgp_user__scgp_bus__id=value),
    )
    return qs


def filter_sale_group_scgp_user(qs, _, value):
    qs = qs.filter(
        Q(scgp_user__scgp_sales_groups__id=value)
    )
    return qs


def filter_sale_org_scgp_user(qs, _, value):
    qs = qs.filter(
        Q(scgp_user__scgp_sales_organizations__id=value),
    )
    return qs


def filter_create_date_scgp_user(qs, _, value):
    return filter_range_field(qs, "date_joined__date", value)


def filter_last_update_date_scgp_user(qs, _, value):
    return filter_range_field(qs, "updated_at__date", value)


def filter_last_login_date_scgp_user(qs, _, value):
    return filter_range_field(qs, "last_login__date", value)


def filter_sold_to_scgp_user(qs, _, value):
    if not value:
        return qs
    sold_to_code = value.split("-")[0].strip()
    return qs.filter(
        master_sold_to__sold_to_code=sold_to_code,
    )


class ScgpUsersFilter(django_filters.FilterSet):
    employee_id = django_filters.CharFilter(method=filter_employee_id_scgp_user)
    sold_to = django_filters.CharFilter(method=filter_sold_to_scgp_user)
    last_name = django_filters.CharFilter(method=filter_last_name_scgp_user)
    first_name = django_filters.CharFilter(method=filter_first_name_scgp_user)
    email = django_filters.CharFilter(method=filter_email_scgp_user)
    parent_group = django_filters.NumberFilter(method=filter_parent_group_scgp_user)
    group = django_filters.NumberFilter(method=filter_group_scgp_user)
    update_by = django_filters.CharFilter(method=filter_updated_by_scgp_user)
    status = django_filters.BooleanFilter(method=filter_status_scgp_user)
    bu = django_filters.NumberFilter(method=filter_bu_scgp_user)
    sale_group = django_filters.NumberFilter(method=filter_sale_group_scgp_user)
    sale_org = django_filters.NumberFilter(method=filter_sale_org_scgp_user)
    create_date = ObjectTypeFilter(input_class=DateRangeInput, method=filter_create_date_scgp_user)
    last_update_date = ObjectTypeFilter(input_class=DateRangeInput, method=filter_last_update_date_scgp_user)
    last_login_date = ObjectTypeFilter(input_class=DateRangeInput, method=filter_last_login_date_scgp_user)

    class Meta:
        model = User
        fields = ["employee_id", "first_name", "last_name", "create_date", "last_login_date", "email", "parent_group",
                  "group", "update_by", "status",
                  "bu", "sale_group", "sale_org", "last_update_date", "sold_to"]


class ScgpUsersFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ScgpUsersFilter


def search_user_management_sold_to_by_code_or_name(qs, _, value):
    if not value:
        return qs
    return qs.annotate(
        search_text=Concat('sold_to_code', Value(' - '), 'sold_to_name')
    ).filter(search_text__icontains=value)


def filter_account_group_code(qs, _, value):
    if value:
        qs = qs.filter(account_group_code__in=value)
    return qs


class UserManagementSoldToFilter(MetadataFilterBase):
    search = django_filters.CharFilter(method=search_user_management_sold_to_by_code_or_name)
    account_group_code = ListObjectTypeFilter(input_class=graphene.String, method=filter_account_group_code)

    class Meta:
        model = sap_data_models.SoldToMaster
        fields = ["id", "account_group_code"]


class UserManagementSoldToFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = UserManagementSoldToFilter


def search_sale_org_by_bu(qs, _, value):
    if not value:
        return qs
    return qs.filter(business_unit__name__in=value)


class UserManagementSaleOrgFilter(MetadataFilterBase):
    business_unit = ListObjectTypeFilter(input_class=graphene.String, method=search_sale_org_by_bu)

    class Meta:
        model = sap_data_models.SalesOrganizationMaster
        fields = ["business_unit"]


class UserManagementSaleOrgFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = UserManagementSaleOrgFilter


def search_sales_group_by_sale_org(qs, _, value):
    if not value:
        return qs
    return qs.filter(sales_organization__code__in=value)


class UserManagementSalesGroupFilter(MetadataFilterBase):
    sales_organization = ListObjectTypeFilter(input_class=graphene.String, method=search_sales_group_by_sale_org)

    class Meta:
        model = sap_migration.models.SalesGroupMaster
        fields = ["sales_organization"]


class UserManagementSalesGroupFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = UserManagementSalesGroupFilter


def search_sales_office_by_sale_org(qs, _, value):
    if not value:
        return qs
    return qs.filter(sales_organization__code__in=value)


class UserManagementSaleOfficeFilte(MetadataFilterBase):
    sales_organization = ListObjectTypeFilter(input_class=graphene.String, method=search_sales_office_by_sale_org)

    class Meta:
        model = sap_migration.models.SalesGroupMaster
        fields = ["sales_organization"]


class UserManagementSaleOfficeFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = UserManagementSaleOfficeFilte
