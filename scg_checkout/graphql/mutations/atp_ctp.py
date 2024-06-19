import graphene
import logging
from django.core.exceptions import ValidationError

from saleor.graphql.core.mutations import BaseMutation
from sap_migration.graphql.enums import InquiryMethodType
from scg_checkout.graphql.implementations.atp_ctp import (
    change_order_call_atp_ctp_request,
    change_order_call_atp_ctp_confirm
)
from scg_checkout.graphql.mutations.order import IPlanMessage

from scg_checkout.graphql.contract_checkout_error import ContractCheckoutError
from scg_checkout.graphql.types import SapOrderMessage, SapItemMessage
from scgp_export.graphql.enums import ATPCTPActionType


class CheckoutATPCTPItemBaseListItem:
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


class CheckoutATPCTPItemBaseListItemInput(graphene.InputObjectType, CheckoutATPCTPItemBaseListItem):
    pass


class CheckoutATPCTPItemBaseListItemOutput(graphene.ObjectType, CheckoutATPCTPItemBaseListItem):
    pass


class CheckoutATPCTPItemBase:
    original_item_no = graphene.String(required=True)
    material_variant_code = graphene.String(required=True)
    material_variant_description = graphene.String()
    original_quantity = graphene.Float(required=True)
    original_request_date = graphene.String(required=True)
    original_plant = graphene.String()
    order_no = graphene.String()
    line_id = graphene.ID()
    list_items = graphene.List(CheckoutATPCTPItemBaseListItemOutput)


class CheckoutATPCTPRequestResultType(graphene.ObjectType, CheckoutATPCTPItemBase):
    pass


class CheckoutATPCTPConfirmItemInputType(graphene.InputObjectType, CheckoutATPCTPItemBase):
    action = ATPCTPActionType()
    calculated_item_no = graphene.String()
    list_items = graphene.List(CheckoutATPCTPItemBaseListItemInput)


class CheckoutATPCTPConfirmItemOutputType(graphene.ObjectType, CheckoutATPCTPItemBase):
    action = ATPCTPActionType()
    calculated_item_no = graphene.String()


class CheckoutATPCTPRequestOrderLineInput(graphene.InputObjectType):
    order_no = graphene.String()
    item_no = graphene.String()
    request_date = graphene.String()
    line_id = graphene.ID()
    quantity = graphene.String()
    plant = graphene.String()
    inquiry_method = InquiryMethodType()
    consignment_location = graphene.String()


class CheckoutChangeOrderATPCTPRequestMutation(BaseMutation):
    items = graphene.List(
        graphene.NonNull(CheckoutATPCTPRequestResultType), default_value=[]
    )
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    items_failed = graphene.List(
        graphene.NonNull(CheckoutATPCTPRequestResultType), default_value=[]
    )

    class Arguments:
        order_lines = graphene.List(
            CheckoutATPCTPRequestOrderLineInput,
            description="List of order line.",
            required=True,
        )

    class Meta:
        description = "atp ctp request mutation"
        error_type_class = ContractCheckoutError

    @classmethod
    def perform_mutation(cls, root, info, **data):
        items, i_plan_messages, items_failed = change_order_call_atp_ctp_request(
            info.context.plugins,
            data.get("order_lines"),
        )
        return CheckoutChangeOrderATPCTPRequestMutation(
            items=items,
            i_plan_messages=i_plan_messages,
            items_failed=items_failed
        )


class CheckoutATPCTPConfirmInputType(graphene.InputObjectType):
    items = graphene.List(
        CheckoutATPCTPConfirmItemInputType,
        required=True
    )


class CheckoutChangeOrderATPCTPConfirmMutation(BaseMutation):
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    sap_order_messages = graphene.List(SapOrderMessage)
    sap_item_messages = graphene.List(SapItemMessage)
    items = graphene.List(
        CheckoutATPCTPConfirmItemOutputType
    )

    class Arguments:
        input = CheckoutATPCTPConfirmInputType(required=True)

    class Meta:
        description = "atp ctp confirm mutation"
        error_type_class = ContractCheckoutError

    @classmethod
    def validate_input_items(cls, items):
        if not items:
            raise ValidationError(
                {
                    "items": ValidationError(
                        "list item cannot be empty",
                        code=ContractCheckoutError.INVALID.value,
                    )
                }
            )

    @classmethod
    def perform_mutation(cls, root, info, **data):
        logging.info(f"[Domestic: ATP/CTP Accept/RollBack] FE request: {data}, by user : {info.context.user}")
        input_data = data.get("input")
        cls.validate_input_items(input_data.get("items"))
        sap_order_messages, sap_item_messages, i_plan_messages, items = change_order_call_atp_ctp_confirm(info.context.plugins, input_data)
        return CheckoutChangeOrderATPCTPConfirmMutation(
            sap_order_messages=sap_order_messages,
            sap_item_messages=sap_item_messages,
            i_plan_messages=i_plan_messages,
            items=items
        )
