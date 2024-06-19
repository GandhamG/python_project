import graphene
from django.db.models import QuerySet, Count, IntegerField
from django.db.models.functions import Cast
from graphene import InputObjectType

from saleor.graphql.core.enums import OrderDirection
from saleor.graphql.core.types import SortInputObjectType


class ContractsSortField(graphene.Enum):
    CONTRACT_NO = ["code", "pk"]

    @property
    def description(self):
        if self.name in ContractsSortField.__enum__._member_names_:
            sort_name = self.name.lower().replace("_", " ")
            return f"Sort contracts by {sort_name}."
        raise ValueError("Unsupported enum value: %s" % self.value)


class ContractsSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = ContractsSortField
        type_name = "contracts"


class ScgProductOrderField(graphene.Enum):
    TOTAL_QUANTITY = ["total_quantity", "pk"]
    REMAINING_QUANTITY = ["remaining_quantity", "pk"]
    PRICE_PER_UNIT = ["price_per_unit", "pk"]


class ProductSortingInput(InputObjectType):
    direction = graphene.Argument(
        OrderDirection,
        required=True,
        description="Specifies the direction in which to sort products.",
    )
    field = graphene.Argument(
        ScgProductOrderField,
        required=True,
        description="Specifies the field in which to sort products.",
    )


class ContractCheckoutsSortField(graphene.Enum):
    LINES_COUNT = ["lines_count", "pk"]

    @property
    def description(self):
        if self.name in ContractCheckoutsSortField.__enum__._member_names_:
            sort_name = self.name.lower().replace("_", " ")
            return f"Sort contract checkouts by {sort_name}."
        raise ValueError("Unsupported enum value: %s" % self.value)

    @staticmethod
    def qs_with_lines_count(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(lines_count=Count("cartlines__id"))


class ContractCheckoutsSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = ContractCheckoutsSortField
        type_name = "contractCheckouts"


class CheckoutLineOrderField(graphene.Enum):
    CONTRACT = ["contract_material__contract__id", "pk"]
    TOTAL = ["contract_material__total_quantity", "pk"]
    REMAIN = ["contract_material__remaining_quantity", "pk"]
    PRICE = ["contract_material__price_per_unit", "pk"]


class CheckoutLineSortingInput(InputObjectType):
    direction = graphene.Argument(
        OrderDirection,
        required=True,
        description="Specifies the direction in which to sort checkout lines.",
    )
    field = graphene.Argument(
        CheckoutLineOrderField,
        required=True,
        description="Specifies the field in which to sort checkout lines.",
    )


class AlternatedMaterialOsSortField(graphene.Enum):
    SALE_ORG = ["alternate_material__sales_organization__code"]
    SOLD_TO = ["alternate_material__sold_to__sold_to_code"]
    MATERIAL_INPUT = ["alternate_material__material_own__material_code"]
    ALTERNATED_MATERIAL = ["material_os__material_code"]
    DIA = ["diameter"]
    TYPE = ["alternate_material__type"]
    PRIORITY = ["priority"]
    LAST_UPDATED_DATE = ["alternate_material__updated_at"]
    LAST_UPDATED_BY = ["alternate_material__updated_by__first_name"]


class AlternativeMaterialOsInput(SortInputObjectType):
    direction = graphene.Argument(
        OrderDirection,
        required=True,
        description="Specifies the direction in which to sort alter material os.",
    )
    field = graphene.Argument(
        AlternatedMaterialOsSortField,
        required=True,
        description="Specifies the field in which to sort alter material os.",
    )

    class Meta:
        sort_enum = AlternatedMaterialOsSortField
        type_name = "alternatedMaterial"


class OrderDraftField(graphene.Enum):
    UPDATED_AT = ["updated_at", "pk"]
    CREATED_AT = ["created_at", "pk"]
    SOLD_TO = ["sold_to__sold_to_code", "pk"]
    CONTRACT_NO = ["contract__code", "pk"]


class OrderDraftSorterInput(SortInputObjectType):
    direction = graphene.Argument(
        OrderDirection,
        required=True
    )
    field = graphene.Argument(
        OrderDraftField,
        required=True,
    )

    class Meta:
        sort_enum = OrderDraftField
        type_name = "orderDrafts"


class DomesticOrderSortField(graphene.Enum):
    SO_NO = ["so_no", "pk"]


class DomesticOrderSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = DomesticOrderSortField
        type_name = "domesticOrders"


class DomesticOrderLinesSortField(graphene.Enum):
    ITEM_NO = ["item_no_int", "pk"]

    @staticmethod
    def qs_with_item_no(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(item_no_int=Cast('item_no', output_field=IntegerField()))


class DomesticOrderLinesSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = DomesticOrderLinesSortField
        type_name = "orderLines"


class AlternatedMaterialSortField(graphene.Enum):
    ORDER_NO = ["order_no_int", "pk"]

    @staticmethod
    def qs_with_order_no(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(order_no_int=Cast('order__so_no', output_field=IntegerField()))


class AlternatedMaterialSortInput(SortInputObjectType):
    class Meta:
        sort_enum = AlternatedMaterialSortField
        type_name = "alternatedMaterial"


class DomesticOrderConfirmationSortField(graphene.Enum):
    SO_NO = ["so_no", "pk"]


class DomesticOrderConfirmationSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = DomesticOrderConfirmationSortField
        type_name = "orderConfirmation"
