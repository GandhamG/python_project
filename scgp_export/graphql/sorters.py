import graphene
from saleor.graphql.core.types import SortInputObjectType


class ExportPIsSortField(graphene.Enum):
    CODE = ["code", "pk"]

    @property
    def description(self):
        if self.name in ExportPIsSortField.__enum__._member_names_:
            sort_name = self.name.lower().replace("_", " ")
            return f"Sort customer carts by {sort_name}."
        raise ValueError("Unsupported enum value: %s" % self.value)


class ExportPIsSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = ExportPIsSortField
        type_name = "exportPIs"


class ExportOrderLinesSortField(graphene.Enum):
    MATERIAL_CODE = ["material_code"]

    @property
    def description(self):
        if self.name in ExportOrderLinesSortField.__enum__._member_names_:
            sort_name = self.name.lower().replace("_", " ")
            return f"Sort order lines by {sort_name}."
        raise ValueError("Unsupported enum value: %s" % self.value)


class ExportOrderLinesSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = ExportOrderLinesSortField
        type_name = "order_lines"


class ScgExportCartOrderField(graphene.Enum):
    SOLD_TO = ["sold_to__sold_to_code", "sold_to__sold_to_name", 'pk']


class ExportCartSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = ScgExportCartOrderField
        type_name = "exportCart"


class ScgExportCartItemOrderField(graphene.Enum):
    REMAINING_QUANTITY = ["contract_material__remaining_quantity", 'pk']
    TOTAL_QUANTITY = ["contract_material__total_quantity", "pk"]
    PRICE_PER_UNIT = ["contract_material__price_per_unit", "pk"]
    CONTRACT_MATERIAL_ID = ["contract_material__id", "pk"]


class ExportCartItemSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = ScgExportCartItemOrderField
        type_name = "exportCartItem"


class ExportPIProductsSortField(graphene.Enum):
    REMAINING_QUANTITY = ["remaining_quantity", "pk"]
    TOTAL_QUANTITY = ["total_quantity", "pk"]
    PRICE_PER_UNIT = ["price_per_unit", "pk"]
    ITEM_NO = ["item_no", "pk"]


class ExportPIProductsSortingInput(SortInputObjectType):
    field = graphene.Argument(
        ExportPIProductsSortField,
        required=True,
        description="Specifies the field in which to sort products.",
    )

    class Meta:
        sort_enum = ExportPIProductsSortField
        type_name = "exportPiProducts"


class ExportOrderSortField(graphene.Enum):
    PI_NO = ["contract__code", "pk"]


class ExportOrderSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = ExportOrderSortField
        type_name = "exportOrders"
