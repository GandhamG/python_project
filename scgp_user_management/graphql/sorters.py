import graphene
from django.contrib.postgres.aggregates import StringAgg
from django.db.models import QuerySet, Value
from django.db.models.functions import Coalesce

from saleor.graphql.core.types import SortInputObjectType
from scgp_user_management.graphql.helpers import thai_collage_field


class ScgpUserSortField(graphene.Enum):
    EMPLOYEE_ID = ["scgp_user__employee_id", "pk"]
    CREATED_DATE = ["date_joined", "pk"]
    USER_GROUP = ["scgp_user__user_parent_group__name", "pk"]
    BU = ["bu", "pk"]
    SALE_ORGANIZATION = ["sale_organization", "pk"]
    SALE_GROUP = ["sale_group", "pk"]
    FIRST_NAME = ["first_name_collate", "pk"]
    LAST_NAME = ["last_name_collate", "pk"]

    @staticmethod
    def qs_with_sale_organization(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(sale_organization=Coalesce(
            StringAgg(
                "scgp_user__scgp_sales_organizations__name",
                delimiter=", ",
                ordering="-scgp_user__scgp_sales_organizations__name",
            ), Value("")
        ))

    @staticmethod
    def qs_with_sale_group(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(sale_group=Coalesce(
            StringAgg(
                "scgp_user__scgp_sales_groups__name",
                delimiter=", ",
                ordering="-scgp_user__scgp_sales_groups__name",
            ), Value("")
        ))

    @staticmethod
    def qs_with_bu(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(bu=Coalesce(
            StringAgg(
                "scgp_user__scgp_bus__name",
                delimiter=", ",
                ordering="-scgp_user__scgp_bus__name",
            ), Value("")
        ))

    @staticmethod
    def qs_with_first_name(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(first_name_collate=Coalesce(
            thai_collage_field("first_name"), Value("")
        ))

    @staticmethod
    def qs_with_last_name(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(last_name_collate=Coalesce(
            thai_collage_field("last_name"), Value("")
        ))


class ScgpUserSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = ScgpUserSortField
        type_name = "scgpUser"
