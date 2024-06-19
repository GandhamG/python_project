import graphene
from django.db.models import QuerySet, Count, IntegerField
from django.db.models.functions import Cast

from saleor.graphql.core.types import SortInputObjectType
from saleor.graphql.core.enums import OrderDirection


class ScgpCustomerProductOrderField(graphene.Enum):
    TOTAL = ["total_quantity", "pk"]
    REMAIN = ["remaining_quantity", "pk"]
    PRICE = ["price_per_unit", "pk"]


class CustomerProductSortingInput(graphene.InputObjectType):
    direction = graphene.Argument(
        OrderDirection,
        required=True,
        description="Specifies the direction in which to sort products.",
    )
    field = graphene.Argument(
        ScgpCustomerProductOrderField,
        required=True,
        description="Specifies the field in which to sort products.",
    )


class CustomerCartsSortField(graphene.Enum):
    LINES_COUNT = ["lines_count", "pk"]

    @property
    def description(self):
        if self.name in CustomerCartsSortField.__enum__._member_names_:
            sort_name = self.name.lower().replace("_", " ")
            return f"Sort customer carts by {sort_name}."
        raise ValueError("Unsupported enum value: %s" % self.value)

    @staticmethod
    def qs_with_lines_count(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(lines_count=Count("cartlines__id"))


class CustomerCartsSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = CustomerCartsSortField
        type_name = "customerCarts"


class OrderLinesSortField(graphene.Enum):
    ITEM_NO = ["item_no_int", "pk"]

    @staticmethod
    def qs_with_item_no(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(item_no_int=Cast('item_no', output_field=IntegerField()))


class OrderLinesSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = OrderLinesSortField
        type_name = "orderLines"


class CustomerOrderSortField(graphene.Enum):
    SO_NO = ["so_no", "pk"]


class CustomerOrderSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = CustomerOrderSortField
        type_name = "customerOrders"


class CustomerOrderConfirmationSortField(graphene.Enum):
    SO_NO = ["so_no", "pk"]


class CustomerOrderConfirmationSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = CustomerOrderConfirmationSortField
        type_name = "orderConfirmation"
