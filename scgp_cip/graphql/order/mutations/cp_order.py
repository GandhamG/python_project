from saleor.graphql.core.mutations import ModelMutation
import graphene
from sap_migration import models as migration_models
from scgp_cip.graphql.order.cip_order_error import CipOrderError
from scgp_cip.graphql.order.types import SapOrderMessages, CPItemMessage, CPMessage, SapItemMessages, CipTempOrder, \
    CpOrderLineInput, CpOrderUpdateInput, WarningMessages
from scgp_cip.service.create_order_service import create_or_update_cp_order
from scgp_cip.service.helper.create_order_helper import get_response_message


class CpOrderCreate(ModelMutation):
    success = graphene.Boolean()
    sap_order_number = graphene.String()
    sap_order_status = graphene.String()
    sap_order_messages = graphene.List(SapOrderMessages)
    cp_item_messages = graphene.List(CPItemMessage)
    cp_error_messages = graphene.List(CPMessage)
    sap_item_messages = graphene.List(SapItemMessages)
    warning_messages = graphene.List(WarningMessages)

    class Arguments:
        input = CpOrderUpdateInput(required=True, description="CIP order input data")

    class Meta:
        description = "update order"
        model = migration_models.Order
        object_type = CipTempOrder
        return_field_name = "order"
        error_type_class = CipOrderError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        # cls.validate_input(data)
        res = create_or_update_cp_order(data, info)
        try:
            order = res.get('order')
        except AttributeError:
            order = None

        try:
            cp_item_messages = res.get('cp_item_messages')
        except AttributeError:
            cp_item_messages = None

        try:
            cp_error_messages = res.get('cp_error_messages')
        except AttributeError:
            cp_error_messages = None

        try:
            sap_item_messages = res.get('sap_item_messages')
        except AttributeError:
            sap_item_messages = None

        try:
            sap_order_messages = res.get('sap_order_messages')
        except AttributeError:
            sap_order_messages = None

        try:
            warning_messages = res.get('warning_messages')
        except AttributeError:
            warning_messages = None

        try:
            success = res.get("success")
        except AttributeError:
            success = None

        # Add checks for each variable before passing them to get_response_message
        response = get_response_message(
                cls.success_response(res) if cls.success_response(res) else None,
                order,
                success,
                cp_item_messages,
                cp_error_messages,
                sap_order_messages,
                sap_item_messages,
                warning_messages
        )
        return response