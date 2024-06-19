import graphene
from django.core.exceptions import ValidationError

from saleor.graphql.core.mutations import BaseMutation
from scg_checkout.graphql.mutations.order import IPlanMessage
from scg_checkout.graphql.types import SapOrderMessage, SapItemMessage
from scgp_export.graphql.enums import ATPCTPActionType
from scgp_export.graphql.scgp_export_error import ScgpExportError
from scgp_export.implementations.iplan import (
    call_atp_ctp_request,
    call_atp_ctp_confirm,
)
from scgp_export.error_codes import ScgpExportErrorCode


class IplanRequireAttentionRequestParams(object):
    inquiry_method_code = graphene.String()
    use_inventory = graphene.Boolean()
    use_consignment_inventory = graphene.Boolean()
    use_projected_inventory = graphene.Boolean()
    use_production = graphene.Boolean()
    split_order_item = graphene.String()
    single_source = graphene.Boolean()
    re_atp_required = graphene.Boolean()
    fix_source_assignment = graphene.String()
    request_type = graphene.String()
    type_of_delivery = graphene.String()
    transportation_method = graphene.String()


class ATPCTPItems(object):
    item_no = graphene.String()
    quantity = graphene.String()
    confirm_date = graphene.String()
    plant = graphene.String()
    atp_ctp = graphene.String()
    atp_ctp_detail = graphene.String()
    block_code = graphene.String()
    run_code = graphene.String()
    paper_machine = graphene.String()
    unit = graphene.String()
    on_hand_stock = graphene.Boolean()
    order_type = graphene.String()


class ATPCTPListItems(graphene.ObjectType, ATPCTPItems):
    pass


class ATPCTPItemBase(object):
    order_no = graphene.String()
    line_id = graphene.String()
    original_item_no = graphene.String()
    material_variant_code = graphene.String()
    material_variant_description = graphene.String()
    original_quantity = graphene.Float()
    original_request_date = graphene.Date()
    original_plant = graphene.String()
    unique_id = graphene.String()
    list_items = graphene.List(graphene.NonNull(ATPCTPListItems))


class ATPCTPListItemsInput(graphene.InputObjectType, ATPCTPItems):
    pass


class ATPCTPRequestResultType(graphene.ObjectType, ATPCTPItemBase):
    class IPlanRequireAttentionRequestParamsOutput(graphene.ObjectType, IplanRequireAttentionRequestParams):
        pass

    iplan_request_params = graphene.Field(IPlanRequireAttentionRequestParamsOutput)


class RequireAttentionATPCTPRequestResultType(graphene.ObjectType, ATPCTPItemBase):
    class IPlanResponseRequireAttentionRequestParamsOutput(graphene.ObjectType, IplanRequireAttentionRequestParams):
        pass

    iplan_request_params = graphene.Field(IPlanResponseRequireAttentionRequestParamsOutput)


class ATPCTPConfirmItemInputType(graphene.InputObjectType, ATPCTPItemBase):
    class IplanRequireAttentionRequestParamsInput(graphene.InputObjectType, IplanRequireAttentionRequestParams):
        pass

    line_id = graphene.ID()
    action = ATPCTPActionType()
    iplan_request_params = IplanRequireAttentionRequestParamsInput()
    list_items = graphene.List(ATPCTPListItemsInput)


class ATPCTPRequestOrderLineInput(graphene.InputObjectType):
    order_no = graphene.String()
    item_no = graphene.String()


class ATPCTPRequestMutation(BaseMutation):
    items = graphene.List(
        graphene.NonNull(ATPCTPRequestResultType), default_value=[]
    )
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    items_failed = graphene.List(
        graphene.NonNull(ATPCTPRequestResultType), default_value=[]
    )

    class Arguments:
        order_lines = graphene.List(
            ATPCTPRequestOrderLineInput,
            description="List of order line id.",
            required=True,
        )

    class Meta:
        description = "atp ctp request mutation"
        error_type_class = ScgpExportError

    @classmethod
    def perform_mutation(cls, root, info, **data):
        items, i_plan_messages, items_failed = call_atp_ctp_request(info.context.plugins, data.get("order_lines"))
        return ATPCTPRequestMutation(
            items=items,
            i_plan_messages=i_plan_messages,
            items_failed=items_failed
        )


class ATPCTPConfirmInputType(graphene.InputObjectType):
    items = graphene.List(
        ATPCTPConfirmItemInputType,
        required=True
    )


class ATPCTPConfirmMutation(BaseMutation):
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    sap_order_messages = graphene.List(SapOrderMessage, default_value=[])
    sap_item_messages = graphene.List(SapItemMessage, default_value=[])

    class Arguments:
        input = ATPCTPConfirmInputType(required=True)

    class Meta:
        description = "atp ctp confirm mutation"
        error_type_class = ScgpExportError

    @classmethod
    def validate_input_items(cls, items):
        if not items:
            raise ValidationError(
                {
                    "items": ValidationError(
                        "list item cannot be empty",
                        code=ScgpExportErrorCode.INVALID.value,
                    )
                }
            )

    @classmethod
    def perform_mutation(cls, root, info, **data):
        input_data = data.get("input")
        cls.validate_input_items(input_data.get("items"))
        i_plan_messages, sap_order_messages, sap_item_messages = call_atp_ctp_confirm(info.context.plugins, input_data)
        return ATPCTPConfirmMutation(
            i_plan_messages=i_plan_messages,
            sap_order_messages=sap_order_messages,
            sap_item_messages=sap_item_messages,
        )


class RequireAttentionATPCTPRequestMutation(BaseMutation):
    items = graphene.List(
        graphene.NonNull(RequireAttentionATPCTPRequestResultType), default_value=[]
    )
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    items_failed = graphene.List(
        graphene.NonNull(RequireAttentionATPCTPRequestResultType), default_value=[]
    )

    class Arguments:
        order_lines = graphene.List(
            ATPCTPRequestOrderLineInput,
            description="List of order line id.",
            required=True,
        )

    class Meta:
        description = "atp ctp request mutation"
        error_type_class = ScgpExportError

    @classmethod
    def perform_mutation(cls, root, info, **data):
        items, i_plan_messages, items_failed = call_atp_ctp_request(info.context.plugins, data.get("order_lines"))
        return ATPCTPRequestMutation(
            items=items,
            i_plan_messages=i_plan_messages,
            items_failed=items_failed)
