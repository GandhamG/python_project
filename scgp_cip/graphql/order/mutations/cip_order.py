import logging
import time
from functools import reduce

import graphene
from graphene import NonNull, String, Boolean

from saleor.graphql.core.mutations import ModelMutation, BaseMutation
from saleor.graphql.core.types import NonNullList
from scg_checkout.graphql.enums import ScgOrderStatus
from scg_checkout.graphql.helper import round_qty_decimal
from scgp_cip.dao.order_line.order_line_repo import OrderLineRepo
from scgp_cip.graphql.order.types import SapOrderMessages, SapItemMessages, WarningMessages, CPMessage, CPItemMessage
from scg_checkout.graphql.validators import validate_object, validate_objects, validate_delivery_tol
from scgp_cip.common.enum import CipOrderErrorCode, CipOrderInput, OrderInformationSubmit, OrderOrganizationData, OrderLines, \
    OrderType, CIPOrderPaymentType, MaterialTypes
from scgp_cip.graphql.order.cip_order_error import CipOrderError
from scgp_cip.graphql.order.types import CipOrderUpdateInput, CipTempOrder
from sap_migration import models as migration_models
from scgp_cip.graphql.order_line.types import SplitCipOrderLineInput, SplitCipOrderLineInputAfterCp
from scgp_cip.service.change_order_service import duplicate_order_cip
from scgp_cip.service.create_order_service import update_cip_order, create_or_update_cip_order
from scgp_cip.service.helper.change_order_helper import disable_split_flag, enable_split_flag
from scgp_cip.service.helper.create_order_helper import get_response_message
from scgp_cip.service.order_line_service import add_split_cip_order_lines, cp_split_order_lines


class CipOrderUpdate(ModelMutation):
    success = graphene.Boolean()
    sap_order_number = graphene.String()
    order = graphene.Field(CipTempOrder)
    sap_order_status = graphene.String()
    sap_order_messages = graphene.List(SapOrderMessages)
    cp_item_messages = graphene.List(CPItemMessage)
    cp_error_messages = graphene.List(CPMessage)
    sap_item_messages = graphene.List(SapItemMessages)
    warning_messages = graphene.List(WarningMessages)

    class Arguments:
        id = graphene.ID(description="ID of a order to update.", required=True)
        input = CipOrderUpdateInput(required=True, description="CIP order input data")

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
        res = create_or_update_cip_order(data["id"], data["input"], info)
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

    @classmethod
    def validate_input(cls, data):
        if data.get("input").get("status", None) != ScgOrderStatus.CONFIRMED.value:
            return
        validate_object(
            data.get("input").get("order_information", False),
            CipOrderInput.ORDER_INFORMATION.value,
            OrderInformationSubmit.REQUIRED_FIELDS.value,
        )
        validate_object(
            data.get("input").get("order_organization_data", False),
            CipOrderInput.ORDER_ORGANIZATION_DATA.value,
            OrderOrganizationData.REQUIRED_FIELDS.value,
        )
        validate_objects(
            data.get("input").get("lines", []),
            CipOrderInput.LINES.value,
            OrderLines.REQUIRED_FIELDS.value,
        )

        validate_delivery_tol(data.get("input").get("lines", []))

        input_order_lines = data.get("input").get("lines", [])
        for order_line in input_order_lines:
            split_items = order_line.get("split_items", [])
            if len(split_items) == 0:
                continue
            total_split_quantity = reduce(lambda prev, next: prev + next.quantity, split_items, 0)
            line = migration_models.OrderLines.objects.get(pk=order_line.get("id"))
            if line.iplan is None:
                raise ValueError(f"can't split item without iplan")

            if line.original_quantity is None:
                raise ValueError(f"total split quantity of item {line.id} can't be "
                                 "original_quantity null")

            if total_split_quantity > line.iplan.iplant_confirm_quantity \
                    or total_split_quantity > line.original_quantity:
                raise ValueError(f"total split quantity of item {line.id} can't be "
                                 "greater than original item quantity or assigned quantity")

    # cls.validate_quantity(data)


class AddCipSplitOrderLineItem(BaseMutation):
    success = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessages, default_value=[])
    sap_item_messages = graphene.List(SapItemMessages, default_value=[])
    cp_item_messages = graphene.List(CPItemMessage, default_value=[])
    cp_error_messages = graphene.List(CPMessage, default_value=[])

    class Arguments:
        so_no = NonNull(String)
        is_bom = NonNull(Boolean)
        origin_line_items = NonNullList(SplitCipOrderLineInput)
        split_line_items = NonNullList(SplitCipOrderLineInput)

    class Meta:
        description = "Create CIP split order lines"
        error_type_class = CipOrderError
        error_type_field = "errors"

    @classmethod
    def validate_cip_split_input(cls, data):
        if data.get("is_bom"):
            bom_parent_original_line = None
            bom_split_lines = []
            for origin_line in data.get("origin_line_items"):
                if origin_line.is_parent:
                    bom_parent_original_line = origin_line
                    break
            for split_line in data.get("split_line_items"):
                if split_line.is_parent:
                    bom_split_lines.append(split_line)
            cls.validate_cip_order_line_split(bom_parent_original_line, bom_split_lines)

        else:
            original_line = data.get("origin_line_items")[0]
            split_lines = data.get("split_line_items")
            cls.validate_cip_order_line_split(original_line, split_lines)

    @classmethod
    def validate_cip_order_line_split(cls, original_line, split_lines):
        if not original_line.quantity or original_line.quantity == 0:
            raise Exception("Original Line Quantity cannot be 0")
        total_qty = 0
        for split_line in split_lines:
            if not split_line.quantity:
                raise Exception("Split Line Quantity cannot be 0")
            total_qty += int(split_line.quantity)
        origin_lines_db = OrderLineRepo.get_all_related_order_lines(original_line.id)
        if origin_lines_db:
            for item in origin_lines_db:
                cls._validate_cip_split_item(item, original_line, total_qty)
        else:
            raise Exception(f"Order Line {original_line.id} Doesn't Exist")

    @classmethod
    def _validate_cip_split_item(cls, item, original_line, total_qty):
        if CIPOrderPaymentType.CASH.value == item.order.order_type:
            raise Exception(f"Cannot Split Line {original_line.id} ")
        status = item.item_status_en
        assigned_quantity = item.assigned_quantity
        material_type = item.material.material_type if item.material else None
        if item.bom_flag:
            cls._validate_bom(assigned_quantity, item, material_type, original_line, status, total_qty)
        else:
            cls._validate_non_bom(assigned_quantity, item, material_type, original_line, status, total_qty)

    @classmethod
    def _validate_non_bom(cls, assigned_quantity, item, material_type, original_line, status, total_qty):
        if disable_split_flag(item.purch_nos, material_type, status) or \
                not enable_split_flag(assigned_quantity, status):
            raise Exception(f"Cannot Split Line {original_line.id}")
        if round_qty_decimal(item.quantity - total_qty) == 0:
            raise Exception("Original Line Quantity cannot be 0")
        if total_qty > assigned_quantity:
            raise Exception("Exceeding the original quantity")

    @classmethod
    def _validate_bom(cls, assigned_quantity, item, material_type, original_line, status, total_qty):
        if not item.parent:
            if not enable_split_flag(assigned_quantity, status):
                raise Exception(f"Cannot Split Line {original_line.id} ")
            if round_qty_decimal(item.quantity - total_qty) == 0:
                raise Exception("Original Line Quantity cannot be 0")
            if total_qty > assigned_quantity:
                raise Exception("Exceeding the original quantity")
        elif disable_split_flag(item.purch_nos, material_type, status):
            raise Exception(f"Cannot Split Line {original_line.id} as Child BOM doesn't satisfy criteria")

    @classmethod
    def perform_mutation(cls, root, info, **data):
        start_time = time.time()
        so_no = data.get("so_no", "")
        user = info.context.user
        logging.info(
            f"[No Ref Contract -  Change Order:Split] For the order so_no: {so_no},"
            f" by User: {user}. Request is : {data} ")
        cls.validate_cip_split_input(data)
        response = add_split_cip_order_lines(data)
        success = response.get('success')
        sap_order_messages = response.get('sap_order_messages')
        sap_item_messages = response.get('sap_item_messages')
        cp_item_messages = response.get('cp_item_messages')
        cp_error_messages = response.get('cp_error_messages')
        logging.info(f"[No Ref Contract -  Change Order:Split] Time Taken to complete request: "
                     f"for the order so_no: {so_no} by User: {user} is {time.time() - start_time} seconds")
        return cls(success=success, sap_order_messages=sap_order_messages, sap_item_messages=sap_item_messages,
                   cp_item_messages=cp_item_messages, cp_error_messages=cp_error_messages)


class AddCipSplitOrderLineAfterCp(BaseMutation):
    success = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessages, default_value=[])
    sap_item_messages = graphene.List(SapItemMessages, default_value=[])
    cp_item_messages = graphene.List(CPItemMessage, default_value=[])
    cp_error_messages = graphene.List(CPMessage, default_value=[])

    class Arguments:
        so_no = NonNull(String)
        is_bom = NonNull(Boolean)
        origin_line_items = NonNullList(SplitCipOrderLineInputAfterCp)
        split_line_items = NonNullList(SplitCipOrderLineInputAfterCp)

    class Meta:
        description = "Create CIP split order lines after CP Planning"
        error_type_class = CipOrderError
        error_type_field = "errors"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        start_time = time.time()
        so_no = {data.get("so_no", "")}
        user = info.context.user
        logging.info(
            f"[No Ref Contract -  Change Order:Split] After CP Planning"
            f" for the order so_no: {so_no} by User: {user}. Request is : {data} ")
        response = cp_split_order_lines(data)
        success = response.get('success')
        sap_order_messages = response.get('sap_order_messages')
        sap_item_messages = response.get('sap_item_messages')
        cp_item_messages = response.get('cp_item_messages')
        cp_error_messages = response.get('cp_error_messages')
        logging.info(f"[No Ref Contract -  Change Order:Split] Time Taken to complete SAP call after CP Planning "
                     f" for the order so_no: {so_no} by User: {user} "
                     f" is {time.time() - start_time} seconds")
        return cls(success=success, sap_order_messages=sap_order_messages, sap_item_messages=sap_item_messages,
                   cp_item_messages=cp_item_messages, cp_error_messages=cp_error_messages)


class DuplicateOrderCip(ModelMutation):
    class Arguments:
        so_no = graphene.ID(description="ID of a order to duplicate.", required=True)

    class Meta:
        description = "duplicate order"
        model = migration_models.Order
        object_type = CipTempOrder
        return_field_name = "order"
        error_type_class = CipOrderError

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        so_no = data["so_no"]
        new_order = duplicate_order_cip(so_no, info)
        return cls.success_response(new_order)
