import logging
import time

import graphene
from django.core.exceptions import ValidationError

from saleor.graphql.core.mutations import ModelMutation, BaseMutation
from scg_checkout.graphql.contract_checkout_error import ContractCheckoutError
from sap_migration import models as sap_migration_models
from scg_checkout.graphql.enums import OrderLineStatus
from scg_checkout.graphql.types import SapOrderMessage, SapItemMessage
from scgp_cip.graphql.order.cip_order_error import CipOrderError
from scgp_cip.graphql.order.types import CipOrderOtcPartnerInput, CancelDeleteCipOrderLinesInput
from scgp_cip.graphql.order_line.types import CipTempOrderLine
from scgp_cip.service.order_line_service import delete_order_lines, add_order_line, update_otc_ship_to, \
    delete_otc_ship_to, cancel_delete_cip_order_lines, cancel_cip_order, undo_cip_order_lines
from sap_migration import models as migration_models
from scgp_customer.error_codes import ScgpCustomerErrorCode


class DeleteOrderLine(ModelMutation):
    class Arguments:
        ids = graphene.List(
            graphene.ID, description="id of order line to delete", required=True
        )

    class Meta:
        description = "delete order line"
        model = sap_migration_models.OrderLines
        object_type = CipTempOrderLine
        return_field_name = "order_lines"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = delete_order_lines(data["ids"])
        return cls.success_response(result)


class AddOrderLine(ModelMutation):
    order_lines = graphene.List(CipTempOrderLine)
    item_no_updated = graphene.Boolean()

    class Arguments:
        order_id = graphene.String(required=True)
        material_code = graphene.String(required=True)
        id = graphene.ID(required=False)

    class Meta:
        description = "add products to order"
        model = migration_models.OrderLines
        object_type = CipTempOrderLine
        return_field_name = "orderLine"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order_lines, item_no_updated = add_order_line(data)
        return cls(order_lines=order_lines, item_no_updated=item_no_updated)


class UpdateOrderLineOtcShipTo(ModelMutation):
    id = graphene.ID()

    class Arguments:
        line_id = graphene.ID(description="ID of order_line to update.", required=True)
        otc_ship_to = CipOrderOtcPartnerInput(required=True, description="information about One Time Customer Ship TO")

    class Meta:
        description = "update order line otc ship_to"
        model = sap_migration_models.OrderLines
        object_type = CipTempOrderLine
        return_field_name = "order_lines"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = update_otc_ship_to(info, data["line_id"], data["otc_ship_to"])
        return cls(id=result.id)


class DeleteOrderLineOtcShipTo(ModelMutation):
    class Arguments:
        line_id = graphene.ID(description="ID of order_line.", required=True)

    class Meta:
        description = "delete order line otc ship_to"
        model = sap_migration_models.OrderLines
        object_type = CipTempOrderLine
        error_type_class = CipOrderError

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = delete_otc_ship_to(data["line_id"])
        return cls.success_response(result)


class CancelDeleteCipOrderLines(BaseMutation):
    status = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessage, default_value=[])
    sap_item_messages = graphene.List(SapItemMessage, default_value=[])

    class Arguments:
        so_no = graphene.String(required=True)
        order_lines = graphene.List(CancelDeleteCipOrderLinesInput)

    class Meta:
        description = "Cancel Delete Order Lines"
        error_type_class = CipOrderError

    @classmethod
    def validate_input(cls, data):
        order_lines_input = data["order_lines"]
        if not order_lines_input:
            raise ValidationError(
                {
                    "order_lines": ValidationError(
                        "line cannot be empty",
                        code=ScgpCustomerErrorCode.INVALID.value,
                    )
                } )
        for line in order_lines_input:
            if not (line.get("status") and line.get("status") in [
                OrderLineStatus.CANCEL.value,
                OrderLineStatus.DELETE.value, ] ):
                raise ValidationError(
                    {
                        "status": ValidationError(
                            "Status value should either Cancel or Delete",
                            code=ScgpCustomerErrorCode.INVALID.value,
                        )
                    })

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        cls.validate_input(data)
        so_no = data["so_no"]
        order_lines_input = data["order_lines"]

        (
            success,
            sap_order_messages_response,
            sap_item_messages_response
        ) = cancel_delete_cip_order_lines(so_no, order_lines_input, info)
        logging.info(f"[No Ref Contract -  Cancel/Delete] Time Taken to complete FE request: {time.time() - start_time} seconds")
        return cls(status=success, sap_order_messages=sap_order_messages_response,
                   sap_item_messages=sap_item_messages_response)


class CancelCipOrder(BaseMutation):
    status = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessage, default_value=[])
    sap_item_messages = graphene.List(SapItemMessage, default_value=[])

    class Arguments:
        so_no = graphene.String(required=True)
        order_lines = graphene.List(CancelDeleteCipOrderLinesInput)

    class Meta:
        description = "Cancel All  Order Lines"
        error_type_class = CipOrderError

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        (
            success,
            sap_order_messages_response,
            sap_item_messages_response
        ) = cancel_cip_order(data, info)
        logging.info(f"[No Ref Contract - Cancel/Delete] Time Taken to complete FE request: {time.time() - start_time} seconds")
        return cls(status=success, sap_order_messages=sap_order_messages_response,
                   sap_item_messages=sap_item_messages_response)

class CipUndoOrderLines(BaseMutation):
    success = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessage, default_value=[])
    sap_item_messages = graphene.List(SapItemMessage, default_value=[])

    class Arguments:
        so_no = graphene.String(required=True)
        item_no = graphene.List(graphene.String, required=True)

    class Meta:
        description = "Undo Cancel Delete Order Lines"
        error_type_class = CipOrderError


    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        (
            success,
            sap_order_messages,
            sap_item_messages,
        ) = undo_cip_order_lines(data, info)
        return cls(success=success,sap_order_messages=sap_order_messages, sap_item_messages=sap_item_messages)