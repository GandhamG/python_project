import graphene

from saleor.graphql.core.connection import filter_connection_queryset, create_connection_slice
from saleor.graphql.core.fields import FilterConnectionField
from scgp_cip.common.enum import SearchMaterialBy
from scgp_cip.graphql.order.mutations.cip_change_order_add_new_orderline import CipChangeOrderAddNewOrderLine
from scgp_cip.graphql.order_line.filter import MaterialSearchFilterInput
from scgp_cip.graphql.order_line.mutations.order_line import DeleteOrderLine, AddOrderLine, UpdateOrderLineOtcShipTo, \
    DeleteOrderLineOtcShipTo, CancelDeleteCipOrderLines, CancelCipOrder, CipUndoOrderLines
from scgp_cip.graphql.order_line.resolves.order_line import resolve_get_plants_by_mat_code, \
    resolve_search_suggestion_material
from scgp_cip.graphql.order_line.types import PlantResponse, MaterialSearchSuggestionCountableConnection


class CIPOrderLineQueries(graphene.ObjectType):
    get_plants_by_mat_code = graphene.Field(graphene.List(PlantResponse),
                                            material_code=graphene.Argument(graphene.String, required=True),
                                            description="list of plants based on material code")

    search_suggestion_material = FilterConnectionField(
        MaterialSearchSuggestionCountableConnection,
        description="Search suggestion for material",
        filter=MaterialSearchFilterInput(),
        sale_org=graphene.Argument(graphene.String, required=True),
        distribution_channel=graphene.Argument(graphene.String, required=True),
        sold_to=graphene.Argument(graphene.String),
        search_by=graphene.Argument(SearchMaterialBy, description="search by field",
                                    required=True)
    )

    @staticmethod
    def resolve_get_plants_by_mat_code(self, info, **kwargs):
        return resolve_get_plants_by_mat_code(info, kwargs)

    @staticmethod
    def resolve_search_suggestion_material(self, info, **kwargs):
        qs = resolve_search_suggestion_material(info, kwargs)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, MaterialSearchSuggestionCountableConnection
        )


class CIPOrderLineMutation(graphene.ObjectType):
    add_order_line = AddOrderLine.Field()
    delete_order_lines = DeleteOrderLine.Field()
    update_order_line_otc_ship_to = UpdateOrderLineOtcShipTo.Field()
    delete_order_line_otc_ship_to = DeleteOrderLineOtcShipTo.Field()
    cancel_delete_cip_order_lines = CancelDeleteCipOrderLines.Field()
    cancel_cip_order = CancelCipOrder.Field()
    undo_cancel_cip_order_lines = CipUndoOrderLines.Field()
    cip_change_order_add_new_order_line = CipChangeOrderAddNewOrderLine.Field()
