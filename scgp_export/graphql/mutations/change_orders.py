import graphene

from saleor.core.permissions import AuthorizationFilters
from saleor.graphql.core.mutations import BaseMutation
from saleor.graphql.core.types import NonNullList
from scg_checkout.graphql.mutations.order import IPlanMessage
from scg_checkout.graphql.validators import validate_positive_decimal
from scgp_export.graphql.mutations.atp_ctp import ATPCTPRequestResultType, ATPCTPRequestOrderLineInput, \
    ATPCTPRequestMutation
from scgp_export.graphql.mutations.orders import ExportOrderLineAddProductInput, ChangeExportOrderLineAddProductInput

from scgp_export.graphql.scgp_export_error import ScgpExportError
from scgp_export.graphql.types import ExportOrderLine
from scgp_export.graphql.validators import validate_qty_over_remaining, validate_qty_over_remaining_change_export_order
from scgp_export.implementations.change_orders import add_products_to_change_export_order
from scgp_export.implementations.iplan import change_order_call_atp_ctp_request


class ChangeExportOrderAddProducts(BaseMutation):
    result = graphene.List(ExportOrderLine)

    class Arguments:
        id = graphene.ID(description="ID of an order to update.", required=True)
        input = NonNullList(ChangeExportOrderLineAddProductInput, required=True)

    class Meta:
        description = "add product to order"
        return_field_name = "orderLine"
        error_type_class = ScgpExportError
        error_type_field = "scgp_customer_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def validate_input(cls, data):
        for line in data.get("input", []):
            validate_positive_decimal(line.get("quantity", 0))
            # validate_qty_over_remaining(line.get("quantity", 0), line.get("pi_product"))
            # validate_qty_over_remaining_change_export_order(line.get("quantity", 0), line.get("pi_product"), line.get("orderlines_id", []))


    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cls.validate_input(data)
        result = add_products_to_change_export_order(data.get("id"), data.get("input", []), info)
        return cls(result=result)


class ChangeOrderATPCTPRequestOrderLineInput(ATPCTPRequestOrderLineInput):
    line_id = graphene.ID()


class ChangeOrderATPCTPRequestMutation(ATPCTPRequestMutation):
    class Arguments:
        order_lines = graphene.List(
            ChangeOrderATPCTPRequestOrderLineInput,
            description="List of order line.",
            required=True,
        )

    class Meta:
        description = "atp ctp request mutation"
        error_type_class = ScgpExportError

    @classmethod
    def perform_mutation(cls, root, info, **data):
        items, i_plan_messages, items_failed = change_order_call_atp_ctp_request(
            info.context.plugins,
            data.get("order_lines"),
        )
        return ATPCTPRequestMutation(
            items=items,
            i_plan_messages=i_plan_messages,
            items_failed=items_failed
        )
