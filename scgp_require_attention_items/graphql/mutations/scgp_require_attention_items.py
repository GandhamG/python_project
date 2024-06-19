import graphene

from saleor.graphql.core.connection import create_connection_slice
from saleor.graphql.core.mutations import (
    ModelMutation,
    BaseMutation,
)
from saleor.graphql.core.types import NonNullList
from scg_checkout.contract_order_update import cancel_revert_contract_order_lines
from scgp_require_attention_items.graphql.enums import (
    ScgpRequireAttentionTypeOfDelivery,
    ScgpRequireAttentionSplitOrderItemPartialDelivery,
    ScgpRequireAttentionConsignment,
)
from scgp_require_attention_items.graphql.scgp_require_attention_items_error import ScgpRequireAttentionItemsError
from scgp_require_attention_items.implementations.require_attention_items import (
    update_require_attention_item_parameter,
    change_parameter_i_plan,
    pass_parameter_to_i_plan,
    edit_require_attention_items,
    accept_confirm_date_items,
)
from scgp_require_attention_items.graphql.types import (
    ConfirmDate,
    ChangeParameterIPlanType,
    RequireAttentionEditItems,
    ReasonForRejectInput, RequireAttentionCancelDeleteItems,
)
from scgp_require_attention_items.implementations.require_attention_items import (
    accept_confirm_date
)
from scgp_require_attention_items.graphql.types import (
    RequireAttentionItemsCountTableConnection,
    OrderLineIPlan
)
from sap_migration import models as sap_migrations_models
from utils.enums import IPlanInquiryMethodCode


class RequireAttentionItemsDelete(BaseMutation):
    success = graphene.List(RequireAttentionCancelDeleteItems)
    failed = graphene.List(RequireAttentionCancelDeleteItems)
    total_success = graphene.Int()
    total_failed = graphene.Int()

    class Arguments:
        order_line_ids = graphene.List(
            graphene.String, description="IDs of order line to delete."
        )
        reason = ReasonForRejectInput(required=True)

    class Meta:
        description = "delete order line"
        return_field_name = "order_lines"
        error_type_class = ScgpRequireAttentionItemsError
        error_type_field = "scgp_require_attention_items_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        success, failed = cancel_revert_contract_order_lines(data, info)
        return cls(
            errors=[],
            success=success,
            failed=failed,
            total_success=len(success),
            total_failed=len(failed),
        )


class RequireAttentionItemParameterUpdateInput(graphene.InputObjectType):
    inquiry_method_code = graphene.Field(IPlanInquiryMethodCode)
    transportation_method = graphene.Int()
    type_of_delivery = graphene.Field(ScgpRequireAttentionTypeOfDelivery)
    fix_source_assignment = graphene.String()
    split_order_item = graphene.Field(ScgpRequireAttentionSplitOrderItemPartialDelivery)
    partial_delivery = graphene.Field(ScgpRequireAttentionSplitOrderItemPartialDelivery)
    consignment = graphene.Field(ScgpRequireAttentionConsignment)


class RequireAttentionItemsUpdateParameter(ModelMutation):
    class Arguments:
        items_id = graphene.String(description="ID of OrderLine to update", required=True)
        input = RequireAttentionItemParameterUpdateInput(
            required=False, description="Fields required to update require attention items"
        )

    class Meta:
        description = "Update require attention items parameter"
        model = sap_migrations_models.OrderLineIPlan
        object_type = OrderLineIPlan
        return_field_name = "require_attention_items"
        error_type_class = ScgpRequireAttentionItemsError
        error_type_field = "scgp_require_attention_items_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        params = data.get("input")
        items_id = data.get("items_id")
        result = update_require_attention_item_parameter(items_id, params)
        return cls.success_response(result)


class AcceptConfirmDateItemInput(graphene.InputObjectType):
    unique_id = graphene.ID(required=True, description="ID of the pi product.")
    request_date = graphene.Date(required=True)


class AcceptConfirmDateInput(graphene.InputObjectType):
    lines = NonNullList(
        AcceptConfirmDateItemInput,
        description=(
            "A list of RequireAttentionItems items, each containing request_date want "
            "to accept"
        ),
        required=True,
    )


class AcceptConfirmDate(ModelMutation):
    class Arguments:
        input = AcceptConfirmDateInput(required=True, description="Field required to accept confirm date")

    class Meta:
        description = "delete order line"
        model = sap_migrations_models.OrderLines
        object_type = ConfirmDate
        return_field_name = "order_lines"
        error_type_class = ScgpRequireAttentionItemsError
        error_type_field = "scgp_require_attention_items_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = accept_confirm_date(data["input"]["lines"], info)
        success = create_connection_slice(
            result[0], info, data, RequireAttentionItemsCountTableConnection
        )
        failed = create_connection_slice(
            list(result[1]), info, data, RequireAttentionItemsCountTableConnection
        )
        return cls.success_response([success, failed])


class ChangeParameterIPlan(ModelMutation):
    class Arguments:
        order_line_id = graphene.ID(required=True)

    class Meta:
        description = "delete order line"
        object_type = ChangeParameterIPlanType
        model = sap_migrations_models.OrderLines
        return_field_name = "dropdown"
        error_type_class = ScgpRequireAttentionItemsError
        error_type_field = "scgp_require_attention_items_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = change_parameter_i_plan(data["order_line_id"])
        return cls.success_response(result)


class PassParameterToIPlan(ModelMutation):
    class Arguments:
        order_line_id = graphene.ID(required=True)
        inquiry_method_code = graphene.String(required=True)

    class Meta:
        description = "delete order line"
        model = sap_migrations_models.OrderLines
        object_type = graphene.Boolean
        return_field_name = "status"
        error_type_class = ScgpRequireAttentionItemsError
        error_type_field = "scgp_require_attention_items_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = pass_parameter_to_i_plan(data["order_line_id"], data["inquiry_method_code"])
        return cls.success_response(result)


class EditRequireAttentionItemsInput(graphene.InputObjectType):
    id = graphene.ID(required=True)
    request_date = graphene.Date()
    quantity = graphene.Float()
    item_no = graphene.String()


class EditRequireAttentionInput(graphene.InputObjectType):
    lines = NonNullList(
        EditRequireAttentionItemsInput,
        required=True,
    )


class EditRequireAttentionItems(BaseMutation):
    success = graphene.List(RequireAttentionEditItems)
    failed = graphene.List(RequireAttentionEditItems)
    total_success = graphene.Int()
    total_failed = graphene.Int()

    class Arguments:
        input = EditRequireAttentionInput(required=True, description="Field required to edit items")

    class Meta:
        description = "edit require attention items"
        return_field_name = "order_lines"
        error_type_class = ScgpRequireAttentionItemsError
        error_type_field = "scgp_require_attention_items_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        success, failed = edit_require_attention_items(data["input"]["lines"], info)
        return cls(
            errors=[],
            success=success,
            failed=failed,
            total_success=len(success),
            total_failed=len(failed),
        )


class AcceptConfirmDateRequireAttentionItemsInput(graphene.InputObjectType):
    id = graphene.ID(required=True)
    request_date = graphene.Date()
    item_no = graphene.String()


class AcceptConfirmDateRequireAttentionInput(graphene.InputObjectType):
    lines = NonNullList(
        AcceptConfirmDateRequireAttentionItemsInput,
        required=True,
    )


class AcceptConfirmDateRequireAttentionItems(BaseMutation):
    success = graphene.List(RequireAttentionEditItems)
    failed = graphene.List(RequireAttentionEditItems)
    total_success = graphene.Int()
    total_failed = graphene.Int()

    class Arguments:
        input = AcceptConfirmDateRequireAttentionInput(required=True,
                                                       description="Field required to accept confirm date")

    class Meta:
        description = "accept confirm date items"
        return_field_name = "order_lines"
        error_type_class = ScgpRequireAttentionItemsError
        error_type_field = "scgp_require_attention_items_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        success, failed = accept_confirm_date_items(data["input"]["lines"], info)
        return cls(
            errors=[],
            success=success,
            failed=failed,
            total_success=len(success),
            total_failed=len(failed),
        )
