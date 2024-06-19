import copy
import json
import logging
import time
import uuid
from datetime import date, datetime
from functools import reduce

import graphene
import pytz
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.conf import settings
from graphene import InputObjectType

from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from common.product_group import ProductGroup
from common.newrelic_metric import add_metric_process_order, force_update_attributes
from saleor.core.permissions import AuthorizationFilters
from saleor.graphql.core.mutations import (
    ModelMutation,
    BaseMutation
)
from saleor.graphql.core.types import NonNullList, Error
from saleor.plugins.manager import get_plugins_manager
from sap_master_data import mulesoft_api
from sap_migration import models as migration_models
from scg_checkout.contract_create_order import contract_create_order
from scg_checkout.contract_order_update import (
    add_split_order_line_item,
    contract_order_delete,
    contract_order_line_delete,
    contract_order_lines_delete,
    contract_order_update,
    contract_order_line_all_update,
    delete_split_order_line_item,
    order_lines_update,
    cancel_revert_contract_order_lines,
    print_change_order,
    update_order_line,
    mapping_change_order,
)
from scg_checkout.error_codes import ContractCheckoutErrorCode
from scg_checkout.graphql.contract_checkout_error import ContractCheckoutError
from scg_checkout.graphql.enums import (
    ContractOrder,
    OrderInformation,
    OrderLines,
    OrderOrganizationData,
    ScgOrderStatus,
    OrderLineStatus
)
from scg_checkout.graphql.helper import (
    remapping_i_plan_request,
    call_i_plan_request_get_response,
    call_es21_get_response,
    default_param_yt_65217,
    add_param_iplan_65217,
    call_iplan_65217,
    add_param_to_i_plan_confirm,
    add_param_to_i_plan_request,
    default_param_i_plan_request,
    default_param_es_21,
    add_order_header_to_es_21,
    add_update_item_to_es_21,
    default_param_i_plan_rollback,
    default_param_i_plan_confirm,
    call_i_plan_confirm_get_response,
    remapping_es21,
    save_i_plan_request_response_to_db,
    update_order_line_when_call_es21_success,
    add_new_item_to_es_21,
    save_i_plan_request_response_to_db_for_update_case,
    get_item_no_max_order_line,
    call_rollback_change_order,
    handle_case_iplan_return_split_order,
    save_reason_for_change_request_date, validate_item_status_scenario2_3,
    update_mat_info_and_log_mat_os_after_sap_success, is_order_contract_project_name_special,
    is_other_product_group, compute_iplan_confirm_error_response_and_flag_r5, update_order_when_call_es21_success,
    round_qty_decimal,
)
from scg_checkout.graphql.implementations.change_order import (
    change_order_add_new_item_i_plan_request,
    change_order_add_new_item_es_21,
    change_order_add_new_item_i_plan_confirm,
    call_i_plan_rollback,
    get_iplan_error_messages
)
from scg_checkout.graphql.implementations.change_order_add_product import add_product_to_order
from scg_checkout.graphql.implementations.iplan import send_mail_customer_fail_alternate
from scg_checkout.graphql.implementations.orders import (
    add_products_to_domestic_order,
    print_pdf_order_confirmation,
    prepare_order_confirmation_pdf,
    print_pdf_pending_order_report,
    download_pending_order_report_excel,
    cancel_delete_order_lines,
    undo_order_lines,
)
from scg_checkout.graphql.implementations.sap import (
    get_sap_warning_messages,
    get_error_messages_from_sap_response_for_change_order
)
from scg_checkout.graphql.resolves.orders import call_sap_es26
from scg_checkout.graphql.types import (
    TempOrder,
    TempOrderLine,
    ChangeOrderEditInput,
    SapOrderMessage,
    SapItemMessage,
    IPlanMessage,
    WarningMessage,
    ContractOrderCreateInput,
    ContractOrderUpdateInput,
    DomesticOrderLineAddProductInput,
    ContractOrderLinesUpdateInput,
    UpdateAtpCtpContractOrderLineInput,
    SAPPendingOrderReportInput,
    CancelDeleteOrderLinesInput,
    ChangeOrderAddNewOrderLineInput,
    SendEmailOrderInput,
)
from scg_checkout.graphql.validators import (
    validate_delivery_tol,
    validate_object,
    validate_objects,
    validate_positive_decimal,
    validate_request_date,
    validate_delivery_tolerance
)
from scgp_export.graphql.helper import sync_export_order_from_es26
from scgp_export.implementations.orders import mock_confirmed_date
from scgp_require_attention_items.graphql.helper import update_attention_type_r5, add_class_mark_into_order_line
from sap_migration.graphql.enums import OrderType


class ContractOrderCreate(ModelMutation):
    class Arguments:
        input = ContractOrderCreateInput(
            required=True, description="Fields required to create order"
        )

    class Meta:
        description = "create a new order"
        model = migration_models.Order
        object_type = TempOrder
        return_field_name = "order"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = contract_create_order(info, data["input"])
        return cls.success_response(result)


def get_response_message(response, success, sap_order_messages, sap_item_messages, i_plan_messages, warning_messages):
    response.success = success

    # Return SAP message for order and item
    if len(sap_order_messages):
        response.sap_order_messages = []
        for sap_order_message in sap_order_messages:
            response.sap_order_messages.append(SapOrderMessage(
                error_code=sap_order_message.get("error_code"),
                so_no=sap_order_message.get("so_no"),
                error_message=sap_order_message.get("error_message"),
            ))
    if len(sap_item_messages):
        response.sap_item_messages = []
        for sap_item_message in sap_item_messages:
            response.sap_item_messages.append(SapItemMessage(
                error_code=sap_item_message.get("error_code"),
                item_no=sap_item_message.get("item_no"),
                error_message=sap_item_message.get("error_message"),
            ))
    # Return i-plan message for order
    if len(i_plan_messages):
        response.i_plan_messages = []
        for i_plan_message in i_plan_messages:
            response.i_plan_messages.append(IPlanMessage(
                item_no=i_plan_message.get("item_no"),
                first_code=i_plan_message.get("first_code"),
                second_code=i_plan_message.get("second_code"),
                message=i_plan_message.get("message")
            ))

    if len(warning_messages):
        response.warning_messages = []
        for warning_message in warning_messages:
            response.warning_messages.append(WarningMessage(
                source=warning_message.get("source"),
                order=warning_message.get("order"),
                message=warning_message.get("message")
            ))
    return response


class ContractOrderUpdate(ModelMutation):
    success = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessage)
    sap_item_messages = graphene.List(SapItemMessage)
    i_plan_messages = graphene.List(IPlanMessage)
    warning_messages = graphene.List(WarningMessage)

    class Arguments:
        id = graphene.ID(description="ID of a order to update.", required=True)
        input = ContractOrderUpdateInput(required=True, description="id of order")

    class Meta:
        description = "update order"
        model = migration_models.Order
        object_type = TempOrder
        return_field_name = "order"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def validate_quantity(cls, data):
        input_order_lines = data.get("input", {}).get("lines", [])
        order_lines_dict = {int(x.get('id')): x for x in input_order_lines}
        lines_db = migration_models.OrderLines.all_objects.filter(id__in=order_lines_dict.keys()).in_bulk(
            field_name="id")
        dict_quantity = {}
        dict_remain = {}
        dict_quantity_input = {}

        for key, line in lines_db.items():
            weight = order_lines_dict.get(key).get("weight") if order_lines_dict.get(key).get("weight") else 1
            if line.contract_material.id in dict_quantity_input:
                dict_quantity[line.contract_material.id] += line.quantity * weight * int(not line.draft)
                dict_quantity_input[line.contract_material.id] += order_lines_dict.get(key).get("quantity") * weight
            else:
                dict_quantity[line.contract_material.id] = line.quantity * weight * int(not line.draft)
                dict_remain[line.contract_material.id] = line.contract_material.remaining_quantity
                dict_quantity_input[line.contract_material.id] = order_lines_dict.get(key).get("quantity") * weight

        for key, value in dict_quantity_input.items():
            if value > dict_quantity.get(key, 0) + dict_remain.get(key, 0):
                raise ValueError(f"quantity of item {key} can't be "
                                 "greater than original item quantity or assigned quantity")

    @classmethod
    def validate_input(cls, data):
        if data.get("input").get("status", None) != ScgOrderStatus.CONFIRMED.value:
            return
        validate_object(
            data.get("input").get("order_information", False),
            ContractOrder.ORDER_INFORMATION.value,
            OrderInformation.REQUIRED_FIELDS.value,
        )
        validate_object(
            data.get("input").get("order_organization_data", False),
            ContractOrder.ORDER_ORGANIZATION_DATA.value,
            OrderOrganizationData.REQUIRED_FIELDS.value,
        )
        validate_objects(
            data.get("input").get("lines", []),
            ContractOrder.LINES.value,
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

        cls.validate_quantity(data)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        cls.validate_input(data)
        validate_request_date(
            data.get("id"),
            data.get("input").get("order_information", False)
        )
        (
            result,
            success,
            sap_order_messages,
            sap_item_messages,
            i_plan_messages,
            warning_messages,
            is_validation_error,
            exception_message
        ) = contract_order_update(data["id"], data["input"], info)
        if is_validation_error:
            logging.info(
                f"[Domestic create order] Time Taken to complete FE request: {time.time() - start_time} seconds,"
                f"is_validation_error : {is_validation_error}")
            raise exception_message
        response = get_response_message(
            cls.success_response(result),
            success,
            sap_order_messages,
            sap_item_messages,
            i_plan_messages,
            warning_messages
        )
        diff_time = time.time() - start_time
        logging.info(
            f"[Domestic create order] Time Taken to complete FE request: {diff_time} seconds")
        status = data.get("input").get("status", None)
        if success and status == ScgOrderStatus.CONFIRMED.value:
            add_metric_process_order(
                settings.NEW_RELIC_CREATE_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.DOMESTIC,
                order_id=result.id
            )
        return response


class ContractOrderDelete(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of order to delete.", required=True)

    class Meta:
        description = "delete order"
        model = migration_models.Order
        object_type = TempOrder
        return_field_name = "order"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = contract_order_delete(data["id"])
        return cls.success_response(result)


class ContractOrderLineDelete(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of a order line to delete.", required=True)

    class Meta:
        description = "delete order line"
        model = migration_models.OrderLines
        object_type = TempOrderLine
        return_field_name = "order_line"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = contract_order_line_delete(data["id"])
        return cls.success_response(result)


class ContractOrderLinesDelete(ModelMutation):
    class Arguments:
        ids = graphene.List(
            graphene.ID, description="IDs of a order line to delete.", required=True
        )

    class Meta:
        description = "delete order line"
        model = migration_models.OrderLines
        object_type = TempOrderLine
        return_field_name = "order_lines"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = contract_order_lines_delete(data["ids"])
        return cls.success_response(result)


class FinishOrder(BaseMutation):
    status = graphene.String()

    class Arguments:
        order_id = graphene.ID(
            required=True, description="Id of an order."
        )

    class Meta:
        description = "finish_order"
        error_type_class = ContractCheckoutError
        error_type_field = "finish_order"

    @classmethod
    def get_list_mat_infos(cls, mat):
        code = mat.material_os.code
        grade = code[3:6]
        gram = code[6:9]
        dia = code[14:17]
        return grade, gram, dia

    @classmethod
    def get_list_mat_os(cls, mat_own, sold_to, contract, quantity):
        # Get all alternative mat
        mat_os = migration_models.AlternateMaterialOs.objects.filter(
            alternate_material__material_own=mat_own,
            alternate_material__sold_to=sold_to,
        ).order_by("priority")

        # Get alternative mat infos
        list_oss = []
        list_oss_set = set()
        list_os_info_set = set()
        for mat in mat_os:
            grade, gram, dia = cls.get_list_mat_infos(mat)
            if (grade, gram, dia) not in list_os_info_set:
                # Get all product with the same grade, gram, dia in contract
                regex = f"^.{'{3}'}({grade}{gram}).{'{5}'}({dia}).*$"
                contract_products = migration_models.ContractMaterial.objects.filter(
                    contract=contract,
                    contract__code__iregex=regex,
                ).exclude(material=mat_own)

                for contract_product in contract_products:
                    # Check available quantity in contract
                    if (
                            contract_product.remain >= quantity
                            and contract_product.product not in list_oss_set
                    ):
                        list_oss.append(contract_product.product)
                        list_oss_set.add(contract_product.product)

                list_os_info_set.add((grade, gram, dia))

        return list_oss

    @classmethod
    def call_i_plan(cls, data_set):
        response = {}

        # Mock response
        import random
        for k, v in data_set.items():
            message = random.choice(
                ["Create order with Mat OS", "Create order with Both Mat Own & Mat OS",
                 "Create order with Both Mat Own"]
            )
            response[k] = message
        return response

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order_id = data.get("order_id")
        order = migration_models.Order.objects.get(id=order_id)

        data_set = {}

        sold_to = order.sold_to
        lines = migration_models.OrderLines.objects.filter(order=order)
        for index, line in enumerate(lines):
            data_set[f"line {index + 1}"] = {
                "mat_own": line.product.code
            }

            mat_os = cls.get_list_mat_os(
                line.material,
                sold_to,
                line.contract_material.contract,
                line.quantity
            )

            if mat_os:
                data_set[f"line {index + 1}"]["mat_os"] = [os.code for os in mat_os]

        response = cls.call_i_plan(data_set)

        return cls(
            status=response
        )


class AddProductsToDomesticOrder(ModelMutation):
    order_lines = graphene.List(lambda: TempOrderLine)

    class Arguments:
        id = graphene.ID(description="ID of an order to update.", required=True)
        input = NonNullList(DomesticOrderLineAddProductInput, required=True)

    class Meta:
        description = "add products to order"
        model = migration_models.Order
        object_type = TempOrder
        return_field_name = "order"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def validate_input(cls, data):
        for line in data.get("input", []):
            validate_positive_decimal(line.get("quantity", 0))

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cls.validate_input(data)
        order_lines = add_products_to_domestic_order(data.get("id"), data.get("input", []))
        return cls(order_lines=order_lines)


class ContractOrderLinesUpdate(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of a order to update.", required=True)
        input = ContractOrderLinesUpdateInput(required=True, description="id of order")

    class Meta:
        description = "update order"
        model = migration_models.Order
        object_type = TempOrder
        return_field_name = "order"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def validate_input(cls, data):
        request_date = data.get("request_date")
        if not request_date:
            raise ValidationError(
                {
                    "request_date": ValidationError(
                        f"Request date is required",
                        code=ContractCheckoutErrorCode.REQUIRED.value,
                    )
                }
            )
        elif request_date < date.today():
            raise ValueError(
                f"Request date cannot be less than today",
            )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cls.validate_input(data["input"])
        result = order_lines_update(data["id"], data["input"])
        return cls.success_response(result)


class ContractOrderLineALlUpdate(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of a order to update.", required=True)
        plant = graphene.String()
        request_date = graphene.Date()

    class Meta:
        description = "update all order line"
        model = migration_models.OrderLines
        object_type = graphene.List(TempOrderLine)
        return_field_name = "orderline"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def validate_input(cls, data):
        request_date = data.get("request_date")
        plant = data.get("plant")
        order = migration_models.Order.objects.filter(id=data.get("id")).first()
        if order.status == ScgOrderStatus.CONFIRMED.value:
            return
        if request_date:
            if request_date < date.today():
                raise ValueError("Request date cannot less than today")
        if plant:
            if len(plant) < 4:
                raise ValueError("Plant must be more than 4 digits")

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cls.validate_input(data)
        result = contract_order_line_all_update(data)
        return cls.success_response(result)


class CancelRevertContractOrderLine(ModelMutation):
    class Arguments:
        id = graphene.List(graphene.ID)
        status = graphene.Argument(OrderLineStatus, description='')

    class Meta:
        description = "cancel order line"
        model = migration_models.OrderLines
        object_type = graphene.List(TempOrderLine)
        return_field_name = "orderline"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = cancel_revert_contract_order_lines(data, info)
        return cls.success_response(result)


class PrintOrder(BaseMutation):
    exported_file_base_64 = graphene.String()
    file_name = graphene.String()

    class Arguments:
        order_id = graphene.ID(description="ID of a order to print.", required=True)
        sort_type = graphene.String(description="sort type of a order to print.", required=True)

    class Meta:
        description = "Download PDF order"
        error_type_class = ContractCheckoutError

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order_id = data["order_id"]
        sort_type = data.get("sort_type", "ASC")
        file_name, base64_string = print_change_order(order_id, sort_type)
        return cls(exported_file_base_64=base64_string, file_name=file_name)


class AddSplitOrderLineItemInput(graphene.InputObjectType):
    id = graphene.Int()
    item_no = graphene.String()
    quantity = graphene.Float()
    request_date = graphene.Date()


class AddSplitOrderLineItem(BaseMutation):
    status = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessage, default_value=[])
    sap_item_messages = graphene.List(SapItemMessage, default_value=[])

    class Arguments:
        so_no = graphene.String()
        origin_line_item = AddSplitOrderLineItemInput()
        split_line_items = NonNullList(AddSplitOrderLineItemInput)

    class Meta:
        description = "Create a new split item for order line"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def validate(cls, data):
        if not data.get("origin_line_item").quantity:
            raise Exception("โปรดระบุจำนวนน้อยกว่าจำนวนตั้งต้น")
        total_qty = 0
        for line in data.get("split_line_items"):
            if not line.quantity:
                raise Exception("โปรดระบุจำนวนน้อยกว่าจำนวนตั้งต้น")
            total_qty += int(line.quantity)
        origin_line = migration_models.OrderLines.objects.filter(id=data.get("origin_line_item").id).first()
        if round_qty_decimal(origin_line.quantity - total_qty) == 0:
            raise Exception("โปรดระบุจำนวนน้อยกว่าจำนวนตั้งต้น")

    @classmethod
    def perform_mutation(cls, root, info, **data):
        start_time = time.time()
        logging.info(
            f"[Domestic Split items] For the order so_no: {data.get('so_no', '')}, FE request: {data},by User: {info.context.user}")
        cls.validate(data)
        (
            success,
            sap_order_messages_response,
            sap_item_messages_response
        ) = add_split_order_line_item(data.get("so_no"), data.get("origin_line_item"), data.get("split_line_items"),
                                      info)
        logging.info(f"[Domestic Split items] Time Taken to complete FE request: {time.time() - start_time} seconds")
        if success:
            order = migration_models.Order.objects.filter(so_no=data["so_no"]).first()
            diff_time = time.time() - start_time
            for api_name in ["ES14", "ES15"]:
                force_update_attributes("function", api_name, {"orderId": order.id})
            add_metric_process_order(
                settings.NEW_RELIC_SPLIT_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.DOMESTIC,
                order_id=order.id
            )
        return cls(status=success, sap_order_messages=sap_order_messages_response)


class DeleteSplitOrderLineItem(BaseMutation):
    original_item = graphene.Field(TempOrderLine)

    class Arguments:
        id = graphene.ID()

    class Meta:
        description = "Delete a split item from an order line"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        original_item = delete_split_order_line_item(data["id"])

        return cls(original_item=original_item)


class UpdateContractOrderLine(ModelMutation):
    class Arguments:
        id = graphene.Int(required=True)
        quantity = graphene.Float()
        confirmed_date = graphene.Date()
        plant = graphene.String()

    class Meta:
        description = "update order line"
        model = migration_models.OrderLines
        object_type = TempOrderLine
        return_field_name = "orderline"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        result = update_order_line(root, info, data)
        return cls.success_response(result)


class UpdateAtpCtpContractOrderLine(BaseMutation):
    status = graphene.Boolean()

    class Arguments:
        input = graphene.List(UpdateAtpCtpContractOrderLineInput)

    class Meta:
        description = "update order line"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        status = update_order_line(root, info, data)
        return cls(
            status=status
        )


class PrintPDFOrderConfirmation(BaseMutation):
    exported_file_base_64 = graphene.String()
    file_name = graphene.String()

    class Arguments:
        list_order_confirmation_sap = graphene.Argument(SendEmailOrderInput)

    class Meta:
        description = "Download PDF order"
        return_field_name = "PDF"
        error_type_class = ContractCheckoutError
        error_type_field = "scgp_export_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        list_order_confirmation_sap = data.get("list_order_confirmation_sap")
        file_name, base64_string = print_pdf_order_confirmation(list_order_confirmation_sap)
        return cls(exported_file_base_64=base64_string, file_name=file_name)


class CheckRemainingItemQuantity(BaseMutation):
    remain_quantity = graphene.Float()
    raw_response = graphene.String()

    class Arguments:
        item_no = graphene.String(required=True)
        contract_code = graphene.String(required=True)

    class Meta:
        description = "Check remaining quantity of item in contract"
        return_field_name = "remaining"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        pi_msg_id = str(uuid.uuid1().int)
        param = {
            "piMessageId": pi_msg_id
        }
        uri = f"contracts/{data['contract_code']}"
        response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_get(
            uri,
            param
        )
        response_data = response.get("data", [])
        if (len(response) == 0):
            raise ValueError("There is no response data in SAP API")

        contract_item_list = response_data[0].get("contractItem", [])
        "For now, itemNo from contract will alway format with 6 number string leading by zero"
        item_no_formatted = data.get("item_no").zfill(6)
        matched_contract_items = list(filter(lambda item: item.get("itemNo") == item_no_formatted, contract_item_list))

        if (len(matched_contract_items) == 0):
            raise ValueError("No item with itemNo found from SAP contract")

        return cls(
            remain_quantity=matched_contract_items[0].get("RemainQty"),
            raw_response=json.dumps(response)
        )


class SendOrderEmail(BaseMutation):
    status = graphene.String()

    class Arguments:
        to = graphene.String(required=True)
        cc = graphene.String(required=True)
        subject = graphene.String(required=True)
        content = graphene.String(required=True)
        list_order_confirmation_sap = graphene.List(SendEmailOrderInput)

    class Meta:
        description = "Send Order Email"
        return_field_name = "Email"
        error_type_class = ContractCheckoutError
        error_type_field = "scgp_export_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        try:
            list_attach_file = []
            list_order_confirmation_sap = data.get("list_order_confirmation_sap")
            for order in list_order_confirmation_sap:
                file_name, pdf = prepare_order_confirmation_pdf(order)
                list_attach_file.append(pdf)

            manager = info.context.manager = info.context.plugins
            recipient_list = data["to"].split(",")
            cc_list = data["cc"].split(",")
            subject = data["subject"]
            content = data["content"]

            manager.scgp_send_order_confirmation_email(
                "scg.email",
                recipient_list=recipient_list,
                subject=subject,
                template="order_confirmation_email.html",
                template_data={
                    "content": content
                },
                cc_list=cc_list,
                pdf_file=list_attach_file
            )
            return cls(
                status=True
            )
        except Exception as e:
            raise ValueError(e)


class PrintPendingOrderReport(BaseMutation):
    exported_file_base_64 = graphene.String()
    file_name = graphene.String()

    class Arguments:
        input = SAPPendingOrderReportInput(required=False)

    class Meta:
        description = "Download PDF order"
        return_field_name = "PDF"
        error_type_class = ContractCheckoutError
        error_type_field = "scgp_export_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        file_name, base64_string = print_pdf_pending_order_report(data["input"], info)
        return cls(exported_file_base_64=base64_string, file_name=file_name)


class SendEmailPendingOrder(BaseMutation):
    status = graphene.String()

    class Arguments:
        sold_to_code = graphene.String(required=True)
        list_to = graphene.String(required=True)
        list_cc = graphene.String(required=True)
        subject = graphene.String(required=True)
        email_content = graphene.String(required=True)
        input = SAPPendingOrderReportInput(required=True)

    class Meta:
        description = "Send Email Pending Order"
        return_field_name = "Email"
        error_type_class = ContractCheckoutError
        error_type_field = "email_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        try:
            sold_to_code = data["sold_to_code"]
            create_order_date = timezone.now().astimezone(pytz.timezone("Asia/Bangkok"))
            data_input = data.get("input")
            data_input.sold_to.clear()
            data_input.sold_to.append(sold_to_code)
            if data_input.report_format is None:
                data_input.report_format = "excel"
            file_name, excel_file = download_pending_order_report_excel(data_input, info)
            manager = info.context.manager = info.context.plugins
            recipient_list = data["list_to"].split(",")
            cc_list = data["list_cc"].split(",")
            subject = data["subject"]
            content = data["email_content"]
            file_name_excel = f"PendingOrderReport_{sold_to_code}_{create_order_date.strftime('%d%m%Y')}"\
                if not data_input.get("is_order_tracking", False) \
                else f"Pending_Order_Tracking_{sold_to_code}_{create_order_date.strftime('%d%m%Y')}"
            manager.scgp_send_email_with_excel_attachment(
                "scg.email",
                recipient_list=recipient_list,
                subject=subject,
                template="order_confirmation_email.html",
                template_data={
                    "content": content
                },
                cc_list=cc_list,
                excel_file=excel_file,
                file_name_excel=file_name_excel
            )
            return cls(
                status=True
            )
        except Exception as e:
            raise ValueError(e)


class DownloadPendingOrderReportExcel(BaseMutation):
    exported_file_base_64 = graphene.String()
    file_name = graphene.String()  # Pending Order Report_DDMMYYYY

    class Arguments:
        input = SAPPendingOrderReportInput(required=False)

    class Meta:
        description = "Download Excel pending order"
        return_field_name = "EXCEL"
        error_type_class = ContractCheckoutError
        error_type_field = "scg_checkout_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        data_input = data.get("input")
        file_name, base64_string = download_pending_order_report_excel(data_input, info)
        return cls(exported_file_base_64=base64_string, file_name=file_name)


class CancelDeleteOrderLines(BaseMutation):
    status = graphene.Boolean()
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    sap_order_messages = graphene.List(SapOrderMessage, default_value=[])
    sap_item_messages = graphene.List(SapItemMessage, default_value=[])

    class Arguments:
        so_no = graphene.String(required=True)
        order_lines = graphene.List(CancelDeleteOrderLinesInput)

    class Meta:
        description = "Cancel Delete Order Lines"
        error_type_class = ContractCheckoutError
        error_type_field = "scg_checkout_error"
        return_field_name = "Cancel"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        (
            success,
            i_plan_messages_response,
            sap_order_messages_response,
            sap_item_messages_response
        ) = cancel_delete_order_lines(data, info)
        logging.info(f"[Domestic: Cancel/Delete] Time Taken to complete FE request: {time.time() - start_time} seconds")
        if success:
            # add new case
            order = migration_models.Order.objects.filter(so_no=data["so_no"]).first()
            diff_time = time.time() - start_time
            for api_name in ["ES14", "ES15"]:
                force_update_attributes("function", api_name, {"orderId": order.id})
            add_metric_process_order(
                settings.NEW_RELIC_CHANGE_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.DOMESTIC,
                order_id=order.id
            )
        return cls(status=success, i_plan_messages=i_plan_messages_response,
                   sap_order_messages=sap_order_messages_response, sap_item_messages=sap_item_messages_response)


class UndoOrderLines(BaseMutation):
    success = graphene.Boolean()
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    sap_order_messages = graphene.List(SapOrderMessage, default_value=[])
    sap_item_messages = graphene.List(SapItemMessage, default_value=[])

    class Arguments:
        so_no = graphene.String(required=True)
        item_no = graphene.List(graphene.String, required=True)

    class Meta:
        description = "Cancel Delete Order Lines"
        error_type_class = ContractCheckoutError
        error_type_field = "scg_checkout_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        (
            success,
            i_plan_messages_response,
            sap_order_messages_response,
            sap_item_messages
        ) = undo_order_lines(data, info)
        logging.info(
            f"[Domestic: Undo order lines] Time Taken to complete FE request: {time.time() - start_time} seconds")
        if success:
            order = migration_models.Order.objects.filter(so_no=data["so_no"]).first()
            diff_time = time.time() - start_time
            for api_name in ["ES14", "ES15"]:
                force_update_attributes("function", api_name, {"orderId": order.id})
            add_metric_process_order(
                settings.NEW_RELIC_CHANGE_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.DOMESTIC,
                order_id=order.id
            )
        return cls(success=success, i_plan_messages=i_plan_messages_response,
                   sap_order_messages=sap_order_messages_response, sap_item_messages=sap_item_messages)


class ChangeOrderUpdate(ModelMutation):
    success = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessage)
    sap_item_messages = graphene.List(SapItemMessage)
    i_plan_messages = graphene.List(IPlanMessage)
    sap_warning_messages = graphene.List(WarningMessage)
    iplan_confirm_failed_errors = graphene.List(Error)

    class Arguments:
        so_no = graphene.ID(description="Order SoNo update", required=True)
        input = ChangeOrderEditInput(required=True, description="id of order")

    class Meta:
        description = "update order"
        model = migration_models.Order
        object_type = TempOrder
        return_field_name = "order"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def validate_quantity(cls, data):
        input_order_lines = data.get("input", {}).get("item_details", [])
        order_so_no = data.get("so_no")
        order_lines_dict = {int(order_line.get('item_no')): order_line for order_line in input_order_lines}
        order_lines_db = (
            migration_models.OrderLines.all_objects.filter(
                item_no__in=order_lines_dict.keys(),
                so_no=order_so_no)
            .select_related("contract_material")
            .in_bulk(field_name="id")
        )
        dict_quantity = {}
        dict_remain = {}
        dict_quantity_input = {}
        for key, line in order_lines_db.items():
            weight = order_lines_dict.get(key, {}).get("order_information", {}).get("weight", 1)
            contract_material_id = line.contract_material.id
            '''
            As per SEO-6551 no need to validate ,- After editing the above editable fields values and clicking save, the system could save the change order with success based on validation from SAP
            '''
            prod_group = line.contract_material.mat_group_1
            if is_other_product_group(prod_group):
                continue
            if contract_material_id not in dict_quantity_input:
                dict_quantity[contract_material_id] = 0
                dict_remain[contract_material_id] = line.contract_material.remaining_quantity
                dict_quantity_input[contract_material_id] = 0
            dict_quantity[contract_material_id] += line.quantity * weight * int(not line.draft)
            dict_quantity_input[contract_material_id] += (
                    order_lines_dict.get(key, {}).get("order_information", {}).get("quantity", 0) * weight
            )
        for key, value in dict_quantity_input.items():
            if value > dict_quantity.get(key, 0) + dict_remain.get(key, 0):
                raise ValueError(f"quantity of item {key} can't be "
                                 "greater than original item quantity or assigned quantity")

    @classmethod
    def validate_input(cls, data):
        if data.get("input").get("status", None) != ScgOrderStatus.CONFIRMED.value:
            return
        validate_delivery_tolerance(data.get("input").get("item_details", []))
        cls.validate_quantity(data)

    @classmethod
    def response_edit_order(cls, success, sap_order_messages, sap_item_messages, iplan_response, sap_warning_messages,
                            iplan_confirm_failed_errors):
        return cls(
            success=success,
            sap_order_messages=sap_order_messages,
            sap_item_messages=sap_item_messages,
            i_plan_messages=iplan_response,
            sap_warning_messages=sap_warning_messages,
            iplan_confirm_failed_errors=iplan_confirm_failed_errors
        )

    @classmethod
    @transaction.atomic
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        logging.info(
            f"[Domestic change order] For the order so_no: {data.get('so_no', '')}  request payload from FE :{data}"
            f" by user: {info.context.user}"
        )
        cls.validate_input(data)
        manager = get_plugins_manager()
        iplan_response = []
        sap_order_messages = []
        sap_item_messages = []
        item_error = []
        sap_warning_messages = []
        success = True
        iplan_confirm_failed_errors = []
        order_in_database = (
            migration_models.Order.objects.annotate(
                sale_org_code=F("sales_organization__code"),
                sale_group_code=F("sales_group__code"),
                sold_to__sold_to_code=F("sold_to__sold_to_code")
            )
            .filter(so_no=data["so_no"]).first()
        )
        max_item_no = get_item_no_max_order_line(order_in_database.id)
        edit_header, edit_lines = False, False
        need_iplan_integration = ProductGroup.is_iplan_integration_required(order_in_database)
        logging.info(
            f"[Domestic change Order] is order {data.get('so_no', '')} and product group is "
            f"{order_in_database.product_group}  related to PRODUCT_GROUP_1 : {need_iplan_integration}")
        change_order_mapping = mapping_change_order(order_in_database, data["input"], need_iplan_integration)
        if not change_order_mapping["order_header"] and not change_order_mapping["order_lines_update"]:
            logging.info(
                f"[Domestic change order] Time Taken to complete FE request: {time.time() - start_time} seconds")
            return cls.response_edit_order(success, sap_order_messages, sap_item_messages, iplan_response,
                                           sap_warning_messages, iplan_confirm_failed_errors)
        if change_order_mapping["order_lines_update"]:
            edit_lines = True
        param_i_plan_request = default_param_i_plan_request(data["so_no"])
        param_es_21 = default_param_es_21(data["so_no"])
        param_es_i_plan_rollback = default_param_i_plan_rollback(data["so_no"])
        param_i_plan_confirm = default_param_i_plan_confirm(data["so_no"])
        param_yt_65217 = default_param_yt_65217(data["so_no"])
        flag_es21 = True
        message_error_es21 = None
        change_order_mapping["responseIPlan"] = {}
        while success:
            if change_order_mapping["yt65217"] and edit_lines:
                add_param_iplan_65217(change_order_mapping, param_yt_65217)
                logging.info("[Domestic change order] Calling... iplan YT-65217")
                response_from_es_65217 = call_iplan_65217(manager, param_yt_65217, order_in_database)
                logging.info("[Domestic change order] Called iplan YT-65217")
                iplan_response = get_iplan_error_messages(response_from_es_65217)
                logging.info(f"[Domestic change order] iplan YT-65217 error response: {iplan_response}")
                if iplan_response:
                    success = False
                    continue
                response_lines = response_from_es_65217["OrderUpdateResponse"]["OrderUpdateResponseLine"]
                change_order_mapping["responseIPlan"] = {
                    response_line.get("lineCode").split('.')[0]: response_line for response_line in response_lines}

            if change_order_mapping["yt65156"] and edit_lines:
                add_param_to_i_plan_request(change_order_mapping, param_i_plan_request)
                logging.info("[Domestic change order] Calling... iplan YT-65156")
                response_from_es_65156 = call_i_plan_request_get_response(manager, param_i_plan_request,
                                                                          order_in_database)
                logging.info("[Domestic change order] Called iplan YT-65156")
                iplan_response = get_iplan_error_messages(response_from_es_65156)
                logging.info(f"[Domestic change order] iplan YT-65156 error response: {iplan_response}")
                if iplan_response:
                    for response_line in iplan_response:
                        item_error.append(response_line.get("item_no").split(".")[0])
                    success = False
                    call_rollback_change_order(change_order_mapping, param_es_i_plan_rollback,
                                               manager,
                                               iplan_response, item_error=item_error, order=order_in_database)
                    continue

                i_plan_request_response_line = sorted(
                    response_from_es_65156["DDQResponse"]["DDQResponseHeader"][0]["DDQResponseLine"],
                    key=lambda x: x["lineNumber"])

                for response_line in i_plan_request_response_line:
                    _line_number = response_line.get("lineNumber").split(".")[0]
                    if not change_order_mapping.get("responseIPlan", {}).get(_line_number):
                        line_db = change_order_mapping["order_lines_in_database"].get(_line_number)
                        change_order_mapping["responseIPlan"][_line_number] = copy.deepcopy(response_line)
                        change_order_mapping["order_lines_input"][_line_number]["refDocIt"] = line_db.ref_doc_it.lstrip(
                            "0")
                        change_order_mapping["order_lines_input"][_line_number]["order_information"][
                            "plant"] = response_line.get("warehouseCode")
                        change_order_mapping["order_lines_input"][_line_number][
                            "order_information"].plant = response_line.get("warehouseCode")
                        if line_db and line_db.quantity != change_order_mapping["responseIPlan"][_line_number].get(
                                "quantity") \
                                and not change_order_mapping["order_lines_update"].get(_line_number, {}).get(
                            "quantity"):
                            change_order_mapping["order_lines_update"].setdefault(_line_number, {}).setdefault(
                                "quantity", True)
                    else:
                        max_item_no += 10
                        max_item_no_str = str(max_item_no)
                        change_order_mapping["order_lines_new"][max_item_no_str] = copy.deepcopy(change_order_mapping[
                            "order_lines_input"].get(
                            _line_number))
                        change_order_mapping["order_lines_new"][max_item_no_str]["refDocIt"] = change_order_mapping[
                            "order_lines_in_database"].get(_line_number).ref_doc_it.lstrip("0")
                        change_order_mapping["responseIPlan"].update({max_item_no_str: response_line})
                        change_order_mapping["order_lines_new"][max_item_no_str]["order_information"][
                            "plant"] = response_line.get("warehouseCode")
                        change_order_mapping["order_lines_new"][max_item_no_str][
                            "order_information"].plant = response_line.get("warehouseCode")
                        change_order_mapping["order_lines_new"][max_item_no_str][
                            "order_information"].request_date = response_line.get("dispatchDate")
                        change_order_mapping["order_lines_new"][max_item_no_str]["order_information"][
                            "request_date"] = response_line.get("dispatchDate")
            save_reason_for_change_request_date(change_order_mapping["order_lines_in_database"], change_order_mapping[
                "order_lines_input"])
            if change_order_mapping["order_header"]:
                add_order_header_to_es_21(change_order_mapping, param_es_21)
            if change_order_mapping["order_lines_update"] and edit_lines:
                contract_code = order_in_database.contract.code if order_in_database.contract else ""
                _error, contract_details = mulesoft_api.get_contract_detail(contract_code)
                add_update_item_to_es_21(change_order_mapping, param_es_21, need_iplan_integration,
                                         contract_details=contract_details, order=order_in_database)
            if change_order_mapping["order_lines_new"]:
                add_new_item_to_es_21(change_order_mapping, param_es_21)
            scgp_user = info.context.user.scgp_user
            if scgp_user and scgp_user.sap_id:
                param_es_21["sapId"] = scgp_user.sap_id
            try:
                logging.info("[Domestic change order] Calling ES21")
                response_from_es_21 = call_es21_get_response(manager, param_es_21, order=order_in_database)
                logging.info("[Domestic change order] Called ES21")
            except Exception as e:
                logging.info(f"[Domestic change order] Exception while updating Domestic order from ES21: {e}")
                flag_es21 = False
                message_error_es21 = e.messages[0]
                success = False
                if change_order_mapping["yt65156"]:
                    if sap_order_messages or sap_item_messages or not success:
                        call_rollback_change_order(change_order_mapping, param_es_i_plan_rollback,
                                                   manager,
                                                   message_error_es21,
                                                   exception=True, order=order_in_database)
                continue

            list_item_no = [key for key in change_order_mapping["responseIPlan"].keys()]
            order_lines = migration_models.OrderLines.all_objects.filter(
                order__so_no=data["so_no"],
                item_no__in=list_item_no
            ).distinct("item_no").in_bulk(
                field_name="item_no")
            order_items_out = response_from_es_21.get("orderItemsOut")
            order_line_updates = []
            if order_items_out:
                for item in order_items_out:
                    item_no = item["itemNo"].lstrip("0")
                    order_line = order_lines.get(item_no)
                    if order_line:
                        order_line.weight_unit_ton = item.get('weightUnitTon')
                        order_line.weight_unit = item.get('weightUnit')
                        order_line.net_weight_ton = item.get('netWeightTon')
                        order_line.gross_weight_ton = item.get('grossWeightTon')
                        # Bulk update the fields for the order_line object
                        order_line_updates.append(order_line)
                if order_line_updates:
                    migration_models.OrderLines.objects.bulk_update(order_line_updates,
                                                                    ["weight_unit_ton",
                                                                     "weight_unit", "net_weight_ton",
                                                                     "gross_weight_ton"])
            if flag_es21:
                (
                    sap_order_messages,
                    sap_item_messages,
                    is_being_process,
                    sap_success
                ) = get_error_messages_from_sap_response_for_change_order(response_from_es_21)
                logging.info(f"[Domestic change order] sap_order_error_messages: {sap_order_messages},"
                             f"sap_item_error_messages:{sap_item_messages}")
                sap_warning_messages = get_sap_warning_messages(response_from_es_21)
            if not (sap_order_messages or sap_item_messages) and flag_es21:
                response_lines = response_from_es_21.get("orderSchedulesOut", [])
                change_order_mapping["responseES21"] = {
                    response_line.get("itemNo"): response_line for response_line in response_lines}
            if not edit_lines:
                if sap_order_messages or sap_item_messages:
                    transaction.set_rollback(True)
                    success = False
                else:
                    logging.info(f"[Domestic change order] for the order: {data.get('so_no', '')}"
                                 f" calling ES26 to sync data from SAP to EOR db")
                    response = call_sap_es26(so_no=data["so_no"], order_id=order_in_database.id)
                    sync_export_order_from_es26(response)
                    logging.info("[Domestic change order] called ES26")
                    for api_name in ["ES14", "ES15"]:
                        force_update_attributes("function", api_name, {"orderId": order_in_database.id})
                    diff_time = time.time() - start_time
                    add_metric_process_order(
                        settings.NEW_RELIC_CHANGE_ORDER_METRIC_NAME,
                        int(diff_time * 1000),
                        start_time,
                        "SaveOrder",
                        order_type=OrderType.DOMESTIC,
                        order_id=order_in_database.id
                    )
                logging.info(
                    f"[Domestic change order] Time Taken to complete FE request: {time.time() - start_time} seconds")
                return cls.response_edit_order(success, sap_order_messages, sap_item_messages, iplan_response,
                                               sap_warning_messages, iplan_confirm_failed_errors)
            if change_order_mapping["yt65217"] and sap_order_messages:
                order_lines_fail = []
                for line in change_order_mapping["order_lines_in_database"].values():
                    if line.item_no in change_order_mapping["order_lines_update"] \
                            and validate_item_status_scenario2_3(line.item_status_en):
                        order_lines_fail.append(line)
                update_attention_type_r5(order_lines_fail)
            i_plan_request_remapping = None
            if change_order_mapping["yt65156"]:
                if sap_order_messages or sap_item_messages or not flag_es21:
                    logging.info("[Domestic Change Order] calling.... iplan_rollback as ES21 failed")
                    call_rollback_change_order(change_order_mapping, param_es_i_plan_rollback, manager,
                                               message_error_es21, order=order_in_database)
                    logging.info("[Domestic Change Order] iplan_rollback called")
                    transaction.set_rollback(True)
                    success = False
                    continue
                else:
                    add_param_to_i_plan_confirm(change_order_mapping, param_i_plan_confirm)
                    response_from_es_65156_commit = None
                    try:
                        logging.info("[Domestic Change Order] calling.... iplan_confirm")
                        response_from_es_65156_commit = call_i_plan_confirm_get_response(manager, param_i_plan_confirm,
                                                                                         order=order_in_database)
                        logging.info("[Domestic Change Order] called iplan_confirm")
                    except ValidationError as e:
                        logging.info(f"[Domestic Change Order] ValidationError from i_plan_confirm call : {e}")
                        order_lines_fail = []
                        for line in change_order_mapping["order_lines_in_database"].values():
                            if line.item_no in change_order_mapping["order_lines_update"]:
                                order_lines_fail.append(line)
                        compute_iplan_confirm_error_response_and_flag_r5(e, iplan_confirm_failed_errors,
                                                                         order_lines_fail)
                    if response_from_es_65156_commit:
                        iplan_response = get_iplan_error_messages(response_from_es_65156_commit)
                        logging.info(f"[Domestic Change Order] iplan_confirm error response :{iplan_response}")
                    i_plan_request_remapping = remapping_i_plan_request(response_from_es_65156)
                    if iplan_response:
                        order_lines_fail = []
                        error_item_no = [iplan_error_message.get("item_no") for iplan_error_message in iplan_response]
                        for line in change_order_mapping["order_lines_in_database"].values():
                            if line.item_no in error_item_no:
                                order_lines_fail.append(line)
                        update_attention_type_r5(order_lines_fail)
            if sap_order_messages or sap_item_messages:
                transaction.set_rollback(True)
                success = False
                continue
            logging.info(f"[Domestic change order] for the order: {data.get('so_no', '')}"
                         f" calling ES26 to sync data from SAP to EOR db")
            response = call_sap_es26(so_no=data["so_no"], order_id=order_in_database.id)
            sync_export_order_from_es26(response)
            logging.info("[Domestic change order] called ES26")
            if i_plan_request_remapping:
                save_i_plan_request_response_to_db_for_update_case(i_plan_request_remapping,
                                                                   change_order_mapping)
            mock_confirmed_date(order_in_database)
            # success case
            diff_time = time.time() - start_time
            logging.info(
                f"[Domestic change order] Time Taken to complete FE request: {diff_time} seconds")
            for api_name in ["ES14", "ES15"]:
                force_update_attributes("function", api_name, {"orderId": order_in_database.id})
            add_metric_process_order(
                settings.NEW_RELIC_CHANGE_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.DOMESTIC,
                order_id=order_in_database.id
            )
            return cls.response_edit_order(success, sap_order_messages, sap_item_messages, iplan_response,
                                           sap_warning_messages, iplan_confirm_failed_errors)
        # failed case
        logging.info(
            f"[Domestic change order] Time Taken to complete FE request: {time.time() - start_time} seconds")
        return cls.response_edit_order(success, sap_order_messages, sap_item_messages, iplan_response,
                                       sap_warning_messages, iplan_confirm_failed_errors)


class AddProductToOrderInput(InputObjectType):
    contract_material_id = graphene.ID(required=True)
    material_variant_id = graphene.ID(required=False)
    quantity = graphene.Float(required=True)


class DomesticAddProductToOrder(ModelMutation):
    order_lines = graphene.List(TempOrderLine)

    class Arguments:
        id = graphene.ID(description="ID of an order to update.", required=True)
        input = NonNullList(AddProductToOrderInput, required=True)

    class Meta:
        description = "add products to order"
        model = migration_models.Order
        object_type = TempOrder
        return_field_name = "order"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def validate_input(cls, data):
        for line in data.get("input", []):
            validate_positive_decimal(line.get("quantity", 0))

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cls.validate_input(data)
        order_lines = add_product_to_order(data.get("id"), data.get("input", []))
        return cls(order_lines=order_lines)


class ChangeOrderAddNewOrderLine(BaseMutation):
    success = graphene.Boolean()
    is_redirect_preview = graphene.Boolean()
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    sap_order_messages = graphene.List(SapOrderMessage, default_value=[])
    sap_item_messages = graphene.List(SapItemMessage, default_value=[])
    iplan_confirm_failed_errors = graphene.List(Error)

    class Arguments:
        input = ChangeOrderAddNewOrderLineInput(required=True)

    class Meta:
        description = "Add new order line"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    @transaction.atomic
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        success = True
        is_redirect_preview = False
        manager = get_plugins_manager()
        i_plan_messages_response = []
        sap_order_messages_response = []
        item_error = []
        iplan_confirm_failed_errors = []
        order_headers = data["input"]["order_headers"]
        list_new_items = sorted(data["input"]["list_new_items"], key=lambda x: float(x['item_no']))
        order = migration_models.Order.objects.filter(so_no=order_headers["so_no"]).annotate(
            sale_org_code=F("sales_organization__code"),
            sale_group_code=F("sales_group__code"),
            sold_to__sold_to_code=F("sold_to__sold_to_code")
        ).first()
        logging.info(f"[Domestic: change order Add new items] For the so_no: {order_headers.get('so_no', '')},"
                     f"user:{info.context.user},"
                     f" requested to add new items from FE : {data}")
        qs_new_order_lines = cls.get_new_add_order_lines_info_from_db(list_new_items, order_headers)
        new_items_map = {
            "order_lines_in_database": {order_line.item_no: order_line for order_line in qs_new_order_lines},
            "order_lines_input": {
                order_line["item_no"]: order_line for order_line in data["input"]["list_new_items"]
            }
        }
        need_iplan_integration = ProductGroup.is_iplan_integration_required(order)
        logging.info(
            f"[Domestic: change order Add new items] is order related to PRODUCT_GROUP_1:{need_iplan_integration}")
        response_cls = None
        if need_iplan_integration:
            response_cls = cls.change_order_add_new_with_i_plan(data, i_plan_messages_response, is_redirect_preview,
                                                                item_error,
                                                                list_new_items, manager, need_iplan_integration,
                                                                new_items_map,
                                                                order, order_headers, qs_new_order_lines,
                                                                sap_order_messages_response, success, info,
                                                                iplan_confirm_failed_errors, start_time)

        else:
            response_cls = cls.change_order_add_new_without_i_plan(data, i_plan_messages_response, is_redirect_preview,
                                                                   list_new_items, manager, need_iplan_integration,
                                                                   new_items_map, order, order_headers,
                                                                   qs_new_order_lines,
                                                                   sap_order_messages_response, success, info,
                                                                   start_time)
        if response_cls.success:
            # add new case
            diff_time = time.time() - start_time
            for api_name in ["ES14", "ES15"]:
                force_update_attributes("function", api_name, {"orderId": order.id})
            add_metric_process_order(
                settings.NEW_RELIC_CHANGE_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.DOMESTIC,
                order_id=order.id
            )
        return response_cls

    @classmethod
    def change_order_add_new_without_i_plan(cls, data, i_plan_messages_response, is_redirect_preview, list_new_items,
                                            manager, need_iplan_integration, new_items_map, order, order_headers,
                                            qs_new_order_lines, sap_order_messages_response, success, info, start_time):
        sap_item_message = []
        while success:
            logging.debug(f"Skipping call to iplan for order  {order.order_no} as Iplan integration is false")
            i_plan_request_remapping = {}
            cls.compute_class_mark_for_order_lines(new_items_map, order, qs_new_order_lines)
            logging.info(f"[Domestic: change order Add new items] calling ES21")
            response_es21 = change_order_add_new_item_es_21(order_headers, list_new_items, i_plan_request_remapping,
                                                            manager, new_items_map,
                                                            need_iplan_integration=need_iplan_integration, info=info,
                                                            order=order)
            logging.info(f"[Domestic: change order Add new items] called ES21")
            (
                sap_order_message,
                sap_item_message,
                is_being_process,
                sap_success
            ) = get_error_messages_from_sap_response_for_change_order(response_es21)

            if sap_order_message or sap_item_message:
                logging.info(f"[Domestic: change order Add new items] sap_order_error_message: {sap_order_message},"
                             f"sap_item_error_messages:{sap_item_message}")
                sap_order_messages_response = sap_order_message
                transaction.set_rollback(True)
                success = False
                logging.info(
                    f"[Domestic: change order Add new items] Without iplan call Time Taken to complete FE request: {time.time() - start_time} seconds")
                continue
            is_redirect_preview = True
            logging.debug("Skipping the Iplan back after ES21 success")
            order_items_out = response_es21.get("orderItemsOut")
            update_order_line_when_call_es21_success(need_iplan_integration, data, list_new_items, order_items_out)
            update_order_when_call_es21_success(order, response_es21.get("orderHeaderOut"))
            break
        logging.info(
            f"[Domestic: change order Add new items] Without iplan call Time Taken to complete FE request: {time.time() - start_time} seconds")
        return cls(success=success, is_redirect_preview=is_redirect_preview, i_plan_messages=i_plan_messages_response,
                   sap_order_messages=sap_order_messages_response, sap_item_messages=sap_item_message,
                   iplan_confirm_failed_errors=[])

    @classmethod
    def change_order_add_new_with_i_plan(cls, data, i_plan_messages_response, is_redirect_preview, item_error,
                                         list_new_items, manager, need_iplan_integration, new_items_map, order,
                                         order_headers, qs_new_order_lines, sap_order_messages_response, success, info,
                                         iplan_confirm_failed_errors, start_time):
        sap_item_message = []
        while success:
            response_i_plan_request, alt_mat_i_plan_dict, alt_mat_variant_obj_dict, alt_mat_errors = \
                change_order_add_new_item_i_plan_request(order, qs_new_order_lines, manager)
            i_plan_error_messages = get_iplan_error_messages(response_i_plan_request)
            logging.info(f"[Domestic: change order Add new items] i_plan_error_messages :{i_plan_error_messages}")
            for response_line in i_plan_error_messages:
                item_error.append(response_line.get("item_no").split(".")[0])
            if i_plan_error_messages:
                i_plan_messages_response = i_plan_error_messages
                call_i_plan_rollback(manager, order_headers, list_new_items, item_error=item_error)
                success = False
                logging.info(
                    f"[Domestic: change order Add new items] With iplan Time Taken to complete FE request: {time.time() - start_time} seconds")
                continue
            cls.compute_class_mark_for_order_lines(new_items_map, order, qs_new_order_lines)
            logging.info(f"[Domestic: change order Add new items] calling ES21")
            i_plan_request_remapping, e_ordering_order_lines, new_order_lines, alt_mat_log_changes = \
                handle_case_iplan_return_split_order(response_i_plan_request, list_new_items, qs_new_order_lines,
                                                     order,
                                                     alt_mat_i_plan_dict=alt_mat_i_plan_dict,
                                                     alt_mat_variant_obj_dict=alt_mat_variant_obj_dict)

            response_es21 = change_order_add_new_item_es_21(order_headers, list_new_items, i_plan_request_remapping,
                                                            manager, new_items_map,
                                                            need_iplan_integration=need_iplan_integration, info=info,
                                                            order=order)
            logging.info(f"[Domestic: change order Add new items] called ES21")
            (
                sap_order_message,
                sap_item_message,
                is_being_process,
                sap_success
            ) = get_error_messages_from_sap_response_for_change_order(response_es21)

            if sap_order_message or sap_item_message:
                sap_order_messages_response = sap_order_message
                logging.info(f"[Domestic: change order Add new items] sap_order_error_message: {sap_order_message},"
                             f"sap_item_error_messages:{sap_item_message}")
                logging.info("[Domestic: change order Add new items] iplan roll back Calling as ES21 failed")
                call_i_plan_rollback(manager, order_headers, list_new_items)
                logging.info("[Domestic: change order Add new items] i_plan_roll_back called")
                transaction.set_rollback(True)
                success = False
                logging.info(
                    f"[Domestic: change order Add new items] With iplan call Time Taken to complete FE request: {time.time() - start_time} seconds")
                continue
            is_redirect_preview = True
            logging.debug("calling the Iplan back after ES21 success")
            es21_remapping = remapping_es21(response_es21)
            order_items_out = response_es21.get("orderItemsOut")
            update_order_line_when_call_es21_success(need_iplan_integration, data, list_new_items, order_items_out)
            alt_mat_log_changes.extend(alt_mat_errors)
            update_mat_info_and_log_mat_os_after_sap_success(order, response_es21, alt_mat_log_changes,
                                                             e_ordering_order_lines, new_order_lines)
            response_i_plan_confirm = None
            try:
                logging.info("[Domestic: change order Add new items] calling i_plan_confirm")
                response_i_plan_confirm = change_order_add_new_item_i_plan_confirm(i_plan_request_remapping,
                                                                                   order_headers,
                                                                                   list_new_items, es21_remapping,
                                                                                   manager,
                                                                                   order)
                logging.info("[Domestic: change order Add new items] called i_iplan_confirm")
            except ValidationError as e:
                compute_iplan_confirm_error_response_and_flag_r5(e, iplan_confirm_failed_errors, qs_new_order_lines)
            if response_i_plan_confirm:
                i_plan_error_messages = get_iplan_error_messages(response_i_plan_confirm)
            logging.info(
                f"[Domestic: change order Add new items] i_plan_confirm_error_messages :{i_plan_error_messages}")
            if i_plan_error_messages:
                i_plan_messages_response = i_plan_error_messages
                success = False
                failed_item_no = [message['item_no'] for message in i_plan_error_messages]
                save_i_plan_request_response_to_db(i_plan_request_remapping, list_new_items, response_es21)
                fail_order_line = migration_models.OrderLines.objects.filter(order__so_no=order_headers['so_no'],
                                                                             item_no__in=failed_item_no)
                update_attention_type_r5(fail_order_line)
                logging.info(
                    f"[Domestic: change order Add new items] With iplan call Time Taken to complete FE request: {time.time() - start_time} seconds")
                continue
            save_i_plan_request_response_to_db(i_plan_request_remapping, list_new_items, response_es21)
            try:
                send_mail_customer_fail_alternate(order, manager, alt_mat_errors, True)
            except Exception as e:
                logging.exception(f"[ALT MAT FEATURE] error while sending mail "
                                  f"'Error: Alternated Material auto change':{e}")
            logging.info(
                f"[Domestic: change order Add new items] With iplan call Time Taken to complete FE request: {time.time() - start_time} seconds")
            return cls(success=success, is_redirect_preview=is_redirect_preview,
                       i_plan_messages=i_plan_messages_response,
                       sap_order_messages=sap_order_messages_response,
                       sap_item_messages=sap_item_message,
                       iplan_confirm_failed_errors=iplan_confirm_failed_errors)
        logging.info(
            f"[Domestic: change order Add new items] With iplan call Time Taken to complete FE request: {time.time() - start_time} seconds")
        return cls(success=success, is_redirect_preview=is_redirect_preview, i_plan_messages=i_plan_messages_response,
                   sap_order_messages=sap_order_messages_response,
                   sap_item_messages=sap_item_message,
                   iplan_confirm_failed_errors=iplan_confirm_failed_errors)

    @classmethod
    def compute_class_mark_for_order_lines(cls, new_items_map, order, qs_new_order_lines):
        is_ds_dw_dg = is_order_contract_project_name_special(order)
        if is_ds_dw_dg:
            for order_line in qs_new_order_lines:
                add_class_mark_into_order_line(order_line, "C1", "C", 1, 4)
        save_reason_for_change_request_date(new_items_map["order_lines_in_database"], new_items_map[
            'order_lines_input'])

    @classmethod
    def get_new_add_order_lines_info_from_db(cls, list_new_items, order_headers):
        qs_new_order_lines = migration_models.OrderLines.all_objects.filter(
            order__so_no=order_headers["so_no"],
            item_no__in=[order_line.item_no for order_line in list_new_items]
        )
        for order_line_new in list_new_items:
            for qs_order_line_new in qs_new_order_lines:
                if order_line_new["item_no"] != qs_order_line_new.item_no:
                    continue
                qs_order_line_new.material_code = getattr(getattr(order_line_new, "order_information"), "material_code",
                                                          "")
                qs_order_line_new.plant = getattr(getattr(order_line_new, "order_information"), "plant", "")
                qs_order_line_new.request_date = "-".join(
                    order_line_new["order_information"]["request_date"].split("/")[::-1])
                qs_order_line_new.request_date = datetime.strptime(qs_order_line_new.request_date,
                                                                   "%Y-%m-%d") if qs_order_line_new.request_date else None
                qs_order_line_new.quantity = getattr(getattr(order_line_new, "order_information"), "quantity", 0)

        return qs_new_order_lines

    @classmethod
    def compute_class_mark_for_order_lines(cls, new_items_map, order, qs_new_order_lines):
        is_ds_dw_dg = is_order_contract_project_name_special(order)
        if is_ds_dw_dg:
            for order_line in qs_new_order_lines:
                add_class_mark_into_order_line(order_line, "C1", "C", 1, 4)
        save_reason_for_change_request_date(new_items_map["order_lines_in_database"], new_items_map[
            'order_lines_input'])
