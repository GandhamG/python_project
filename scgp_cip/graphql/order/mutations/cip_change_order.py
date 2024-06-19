import graphene
from django.db import transaction

from saleor.graphql.core.mutations import ModelMutation
from sap_migration import models as migration_models
from scgp_cip.graphql.order.cip_order_error import CipOrderError
from scgp_cip.graphql.order.types import SapOrderMessages, SapItemMessages, WarningMessages, CPMessage, CPItemMessage, \
    CipTempOrder, CipChangeOrderEditInput
from scgp_cip.service.change_order_service import change_cp_order_update, cip_sync_order_data


class CipChangeOrderUpdate(ModelMutation):
    success = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessages)
    sap_item_messages = graphene.List(SapItemMessages)
    cp_item_messages = graphene.List(CPItemMessage)
    cp_error_messages = graphene.List(CPMessage)
    warning_messages = graphene.List(WarningMessages)

    class Arguments:
        input = CipChangeOrderEditInput(required=True, description="id of order")

    class Meta:
        description = "update order"
        model = migration_models.Order
        object_type = CipTempOrder
        return_field_name = "order"
        error_type_class = CipOrderError
        error_type_field = "errors"

    @classmethod
    @transaction.atomic
    def perform_mutation(cls, _root, info, **data):
        response = change_cp_order_update(data)
        success = response.get('success')
        sap_order_messages = response.get('sap_order_messages')
        sap_item_messages = response.get('sap_item_messages')
        cp_item_messages = response.get('cp_item_messages')
        cp_error_messages = response.get('cp_error_messages')
        warning_messages = response.get('warning_messages')
        order = response.get('order')
        return cls(success=success,order=order, sap_order_messages=sap_order_messages, sap_item_messages=sap_item_messages,
                   cp_item_messages=cp_item_messages, cp_error_messages=cp_error_messages, warning_messages=warning_messages)


class CipSyncOrderData(ModelMutation):
    success = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessages)
    sap_item_messages = graphene.List(SapItemMessages)

    class Arguments:
        so_no = graphene.String(required=True)

    class Meta:
        description = "Sync order data"
        model = migration_models.Order
        object_type = CipTempOrder
        return_field_name = "order"
        error_type_class = CipOrderError

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        response = cip_sync_order_data(info, data.get("so_no"))
        return cls.success_response(response)
