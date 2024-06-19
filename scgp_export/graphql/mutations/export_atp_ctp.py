import logging

import graphene
from django.core.exceptions import ValidationError

from saleor.graphql.core.mutations import BaseMutation
from sap_migration.graphql.enums import InquiryMethodType
from scgp_export.graphql.scgp_export_error import ScgpExportError
from scgp_export.implementations.atp_ctp import (
    change_order_call_atp_ctp_request,
    change_order_call_atp_ctp_confirm
)
from scg_checkout.graphql.mutations.order import IPlanMessage

from scg_checkout.graphql.types import SapOrderMessage, SapItemMessage
from scgp_export.graphql.enums import ATPCTPActionType, ScgpExportErrorCode


class ExportATPCTPItemBaseListItem:
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


class ExportATPCTPItemBaseListItemInput(graphene.InputObjectType, ExportATPCTPItemBaseListItem):
    pass


class ExportATPCTPItemBaseListItemOutput(graphene.ObjectType, ExportATPCTPItemBaseListItem):
    pass


class ExportATPCTPItemBase:
    original_item_no = graphene.String(required=True)
    material_variant_code = graphene.String(required=True)
    material_variant_description = graphene.String()
    original_quantity = graphene.Float(required=True)
    original_request_date = graphene.String(required=True)
    original_plant = graphene.String()
    order_no = graphene.String()
    line_id = graphene.ID()
    list_items = graphene.List(ExportATPCTPItemBaseListItemOutput)


class ExportATPCTPRequestResultType(graphene.ObjectType, ExportATPCTPItemBase):
    pass


class ExportATPCTPConfirmItemInputType(graphene.InputObjectType, ExportATPCTPItemBase):
    action = ATPCTPActionType()
    calculated_item_no = graphene.String()
    list_items = graphene.List(ExportATPCTPItemBaseListItemInput)


class ExportATPCTPConfirmItemOutputType(graphene.ObjectType, ExportATPCTPItemBase):
    action = ATPCTPActionType()
    calculated_item_no = graphene.String()


class ExportATPCTPRequestOrderLineInput(graphene.InputObjectType):
    order_no = graphene.String()
    item_no = graphene.String()
    request_date = graphene.String()
    line_id = graphene.ID()
    quantity = graphene.String()
    plant = graphene.String()
    inquiry_method = InquiryMethodType()


class ExportChangeOrderATPCTPRequestMutation(BaseMutation):
    items = graphene.List(
        graphene.NonNull(ExportATPCTPRequestResultType), default_value=[]
    )
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    items_failed = graphene.List(
        graphene.NonNull(ExportATPCTPRequestResultType), default_value=[]
    )

    class Arguments:
        order_lines = graphene.List(
            ExportATPCTPRequestOrderLineInput,
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
        return ExportChangeOrderATPCTPRequestMutation(
            items=items,
            i_plan_messages=i_plan_messages,
            items_failed=items_failed
        )


class ExportATPCTPConfirmInputType(graphene.InputObjectType):
    items = graphene.List(
        ExportATPCTPConfirmItemInputType,
        required=True
    )


class ExportChangeOrderATPCTPConfirmMutation(BaseMutation):
    i_plan_error_messages = graphene.List(IPlanMessage, default_value=[])
    sap_order_error_messages = graphene.List(SapOrderMessage)
    sap_item_messages = graphene.List(SapItemMessage)
    items = graphene.List(
        ExportATPCTPConfirmItemOutputType
    )

    class Arguments:
        input = ExportATPCTPConfirmInputType(required=True)

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
        logging.info(f"[Export: ATP/CTP Accept/RollBack] FE request: {data}, by user : {info.context.user}")
        input_data = data.get("input")
        cls.validate_input_items(input_data.get("items"))
        sap_order_error_messages, sap_item_messages, i_plan_error_messages, items = change_order_call_atp_ctp_confirm(info.context.plugins, input_data)
        return ExportChangeOrderATPCTPConfirmMutation(
            sap_order_error_messages=sap_order_error_messages,
            sap_item_messages=sap_item_messages,
            i_plan_error_messages=i_plan_error_messages,
            items=items
        )
