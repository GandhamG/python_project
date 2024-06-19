import graphene
from django.db.models import QuerySet, Q, Case, When, Value, BooleanField

from saleor.graphql.core.types import SortInputObjectType


class RequireAttentionItemsSortField(graphene.Enum):
    ORDER_NO = ["overdue", "order__so_no", "pk"]
    ITEM_NO = ["overdue", "item_no", "pk"]
    SOLD_TO = ["overdue", "order__contract__sold_to__sold_to_code", "pk"]
    ORIGINAL_DATE = ["overdue", "original_request_date", "pk"]
    REQUEST_DATE = ["overdue", "request_date", "pk"]
    CONFIRM_DATE = ["overdue", "confirmed_date", "pk"]
    REQUEST_QUANTITY = ["overdue", "quantity", "pk"]
    CONFIRM_QUANTITY = ["overdue", "iplan__iplant_confirm_quantity", "pk"]
    UNIT = ["overdue", "material_variant__material__sales_unit", "pk"]
    MATERIAL_CODE = ["overdue", "material_variant__code", "pk"]
    MATERIAL_DESCRIPTION = ["-overdue", "material_variant__description_th", "pk"]
    PO_NO = ["overdue", "order__po_no", "pk"]
    PLANT = ["overdue", "plant", "pk"]
    SHIP_TO = ["overdue", "ship_to", "pk"]
    ITEM_STATUS = ["overdue", "item_status_en", "pk"]
    ORDER_STATUS = ["overdue", "order__status", "pk"]
    ATTENTION_TYPE = ["overdue", "attention_type", "pk"]

    @staticmethod
    def qs_with_order_no(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_item_no(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_sold_to(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_original_date(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_request_date(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_confirm_date(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_request_quantity(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_confirm_quantity(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_unit(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_material_code(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_material_description(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_po_no(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_plant(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_ship_to(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_item_status(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_order_status(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))

    @staticmethod
    def qs_with_attention_type(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(overdue=Case(
            When(Q(overdue_1=True) | Q(overdue_2=True), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ))


class RequireAttentionItemsSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = RequireAttentionItemsSortField
        type_name = "requireAttentionItems"


class SalesOrderSortField(graphene.Enum):
    CREATE_DATE = ["order__created_at", "pk"]
    PO_NO = ["po_no", "pk"]
    ORDER_NO = ["order__so_no", "pk"]
    REQUEST_DATE = ["order__request_date", "pk"]


class SalesOrderSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = SalesOrderSortField
        type_name = "salesOrder"
