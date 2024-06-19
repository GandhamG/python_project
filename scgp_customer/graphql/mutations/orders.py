import time
from datetime import datetime
import graphene
import logging
import time
from django.core.exceptions import ValidationError
from django.conf import settings
from graphene import InputObjectType

from saleor.core.permissions import AuthorizationFilters
from saleor.graphql.core.types import NonNullList
from saleor.graphql.core.mutations import ModelMutation, BaseMutation
from common.newrelic_metric import add_metric_process_order
from scg_checkout.graphql.mutations.order import SapOrderMessage, SapItemMessage, IPlanMessage, WarningMessage, \
    get_response_message
from scg_checkout.graphql.validators import (
    validate_objects,
)
from scgp_customer import models
from scgp_customer.error_codes import ScgpCustomerErrorCode
from scgp_customer.graphql.enums import (
    CustomerOrder as CustomerOrderEnum,
    CustomerOrderLine as CustomerOrderLineEnum,
)
from scgp_customer.graphql.scgp_customer_error import ScgpCustomerError
from scgp_customer.graphql.validators import validate_positive_decimal
from scgp_customer.implementations.orders import (
    update_customer_order,
    create_customer_order,
    add_products_to_order,
    delete_customer_order_lines,
    update_customer_order_lines,
    update_request_date_iplan,
)
from scgp_customer.graphql.types import CustomerOrder
from scgp_require_attention_items.graphql.helper import dtr_dtp_stamp_class_mark, update_attention_type_r1

from sap_migration import models as sap_migration_models
from sap_migration.graphql.enums import OrderType


class CustomerOrderInformationUpdateInput(InputObjectType):
    order_date = graphene.Date()
    order_no = graphene.String()
    request_delivery_date = graphene.Date()
    ship_to = graphene.String()
    bill_to = graphene.String()
    unloading_point = graphene.String()
    remark_for_invoice = graphene.String()
    remark_for_logistic = graphene.String()
    confirm = graphene.Boolean()
    internal_comments_to_warehouse = graphene.String()
    internal_comments_to_logistic = graphene.String()


class CustomerOrderLineUpdateInput(InputObjectType):
    id = graphene.ID(required=True, description="Id of order line")
    quantity = graphene.Float()
    request_delivery_date = graphene.Date()


class CustomerOrderInformationInput(InputObjectType):
    contract_id = graphene.ID(required=True)


class CustomerOrderLineInput(InputObjectType):
    contract_product_id = graphene.ID(required=True)
    variant_id = graphene.ID(required=False)
    quantity = graphene.Float(required=True)
    cart_item_id = graphene.ID(required=True)


class CreateCustomerOrderInput(InputObjectType):
    order_information = graphene.Field(CustomerOrderInformationInput, required=True)
    lines = NonNullList(
        CustomerOrderLineInput,
        required=True,
        description="Order lines"
    )


class CustomerOrderLinesUpdateInput(InputObjectType):
    request_delivery_date = graphene.Date()
    apply_all = graphene.Boolean()
    lines = NonNullList(CustomerOrderLineUpdateInput)


class CustomerOrderUpdate(ModelMutation):
    success = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessage)
    sap_item_messages = graphene.List(SapItemMessage)
    i_plan_messages = graphene.List(IPlanMessage)
    warning_messages = graphene.List(WarningMessage)

    class Arguments:
        id = graphene.ID(description="ID of an order to update.", required=True)
        input = CustomerOrderInformationUpdateInput(required=True)

    class Meta:
        description = "Update customer order"
        model = models.CustomerOrder
        object_type = CustomerOrder
        return_field_name = "order"
        error_type_class = ScgpCustomerError
        error_type_field = "scgp_customer_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        (
            result,
            success,
            sap_order_messages,
            sap_item_messages,
            i_plan_messages,
            warning_messages,
            is_validation_error,
            error_message
        ) = update_customer_order(data.get("id"), data.get("input"), info)
        if is_validation_error:
            raise error_message

        response = get_response_message(
            cls.success_response(result),
            success,
            sap_order_messages,
            sap_item_messages,
            i_plan_messages,
            warning_messages
        )
        logging.info(
            f"[Customer create order] Time Taken to complete FE request: {time.time() - start_time} seconds")
        is_confirmed = data.get("input").get("confirm", False)
        diff_time = time.time() - start_time
        if success and is_confirmed:
            add_metric_process_order(
                settings.NEW_RELIC_CREATE_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.CUSTOMER,
                order_id=result.id
            )
        return response


class CustomerOrderLinesUpdate(ModelMutation):
    class Arguments:
        order_id = graphene.ID(description="ID of an order to update.", required=True)
        input = CustomerOrderLinesUpdateInput()

    class Meta:
        description = "Update customer order lines"
        model = models.CustomerOrder
        object_type = CustomerOrder
        return_field_name = "order"
        error_type_class = ScgpCustomerError
        error_type_field = "scgp_customer_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def validate_input(cls, data):
        for line in data.get("input").get(CustomerOrderEnum.LINES.value, []):
            if type(line.get(CustomerOrderLineEnum.QUANTITY.value, False)) == int or float:
                validate_positive_decimal(line.get(CustomerOrderLineEnum.QUANTITY.value, 0))

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        cls.validate_input(data)
        result = update_customer_order_lines(data.get("order_id"), data.get("input"), info.context.user)
        logging.info(
            f"[customer Create order] update_customer_order_lines Time Taken to complete FE request: {time.time() - start_time} seconds")
        return cls.success_response(result)


class CustomerOrderLinesDelete(ModelMutation):
    class Arguments:
        ids = graphene.List(
            graphene.ID, description="IDs of order line to delete."
        )
        delete_all = graphene.Boolean()
        order_id = graphene.ID()

    class Meta:
        description = "delete order line"
        model = models.CustomerOrderLine
        object_type = graphene.Boolean
        return_field_name = "status"
        error_type_class = ScgpCustomerError
        error_type_field = "scgp_customer_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = delete_customer_order_lines(data.get("ids", []), data.get("delete_all", False),
                                             data.get("order_id", False), info.context.user)
        return cls.success_response(result)


class CustomerOrderAddProduct(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of an order to update.", required=True)
        input = NonNullList(CustomerOrderLineInput, required=True)

    class Meta:
        description = "add product to order"
        model = models.CustomerOrder
        object_type = CustomerOrder
        return_field_name = "order"
        error_type_class = ScgpCustomerError
        error_type_field = "scgp_customer_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def validate_input(cls, data):
        validate_objects(
            data.get("input", False),
            "input",
            CustomerOrderLineEnum.REQUIRED_FIELDS.value
        )
        for line in data.get("input", []):
            validate_positive_decimal(line.get(CustomerOrderLineEnum.QUANTITY.value, 0))

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cls.validate_input(data)
        result = add_products_to_order(data.get("id"), data.get("input", []), info.context.user)
        return cls.success_response(result)


class CreateCustomerOrder(ModelMutation):
    class Arguments:
        input = CreateCustomerOrderInput(
            required=True, description="Fields required to create customer order"
        )

    class Meta:
        description = "create a new order"
        model = sap_migration_models.Order
        object_type = CustomerOrder
        return_field_name = "order"
        error_type_class = ScgpCustomerError
        error_type_field = "checkout_errors"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def validate_input(cls, input_data):
        for line in input_data.get("lines"):
            if line.get("quantity") <= 0:
                raise ValidationError(
                    {
                        "quantity": ValidationError(
                            "quantity must be greater than 0",
                            code=ScgpCustomerErrorCode.INVALID.value,
                        )
                    }
                )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        input_data = data.get("input")
        cls.validate_input(input_data)
        result = create_customer_order(input_data, info)
        return cls.success_response(result)


class UpdateRequestDateOnIplan(BaseMutation):
    status = graphene.Boolean()

    class Arguments:
        order_lines_id = graphene.List(graphene.ID, required=True, description="order line id of order line")
        confirm = graphene.Boolean(required=False, description="confirm or not", default_value=True)

    class Meta:
        description = "Update customer order"
        return_field_name = "order"
        error_type_class = ScgpCustomerError
        error_type_field = "scgp_customer_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        order_line_ids = data["order_lines_id"]
        confirm = data["confirm"]
        status = True
        if confirm:
            status = update_request_date_iplan(order_line_ids)
            dtr_dtp_stamp_class_mark(order_line_ids, "C1")
        else:
            lines = sap_migration_models.OrderLines.objects.filter(id__in=order_line_ids).all()
            update_attention_type_r1(lines)
            sap_migration_models.OrderLines.objects.bulk_update(lines, fields=["attention_type"])
        return cls(
            status=status
        )
