import logging
import time
import uuid
from datetime import date, datetime

import graphene
from graphene import InputObjectType
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.conf import settings

from sap_migration.graphql.enums import InquiryMethodType, OrderType
from scg_checkout.contract_create_order import clone_order
from saleor.core.permissions import AuthorizationFilters
from saleor.graphql.core.mutations import ModelMutation, BaseMutation
from saleor.graphql.core.types import NonNullList
from sap_migration import models
from scg_checkout.graphql.implementations.sap import get_error_messages_from_sap_response_for_change_order
from scg_checkout.graphql.mutations.order import (
    SapOrderMessage,
    SapItemMessage,
    IPlanMessage,
    WarningMessage, get_response_message,
)
from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from common.newrelic_metric import add_metric_process_order, force_update_attributes
from scgp_export.error_codes import ScgpExportErrorCode
from scgp_export.graphql.enums import (
    ScgExportOrderType,
    ScgpExportOrderStatus,
    ScgExportRejectReason,
    SapEnpoint,
    ChangeExportRejectReason
)
from scgp_export.graphql.scgp_export_error import ScgpExportError
from scgp_export.graphql.validators import (
    validate_positive_decimal,
    validate_qty_over_remaining,
)
from scgp_export.implementations.edit_order import flag_r5_failed_items
from scgp_export.implementations.orders import (
    update_export_order,
    create_export_order,
    update_export_order_lines,
    delete_export_order_lines,
    add_products_to_export_order,
    update_all_export_order_lines,
    sync_create_order_to_db,
    duplicate_order,
    cancel_export_order,
    download_pdf_change_order,
    change_parameter_of_export,
    update_inquiry_method_export,
    update_export_order_line_draft,
    cancel_delete_export_order, mock_confirmed_date,
)
from scgp_export.graphql.types import (
    ExportOrderExtended,
    RouteType,
    ExportOrderLine,
)
from scgp_export.implementations.change_order_add_product import add_product_to_order, undo_order_lines_export
from scgp_require_attention_items.graphql.helper import update_attention_type_r5
from scgp_require_attention_items.graphql.types import ChangeParameterIPlanType
from scgp_export.implementations.change_orders import (
    change_order_add_new_items_iplan_request,
    change_order_add_new_item_es_21,
    change_order_add_new_item_i_plan_confirm,
    call_i_plan_rollback,
    add_special_order_line_to_iplan_data_for_call_es21,
    remove_draft_order_lines,
    sync_order_line_add_new_items,
    update_item_status
)
from saleor.plugins.manager import get_plugins_manager
from scg_checkout.graphql.helper import (
    remapping_i_plan_request,
    get_iplan_error_messages,
    remapping_es21,
    update_plant_for_container_line_input, get_error_order_lines_from_iplan_response,
)
from scgp_export.graphql.helper import (
    check_line_is_special_or_container,
    handle_case_iplan_return_split_order,
    save_original_request_date,
    split_lines
)
from scg_checkout.graphql.resolves.orders import call_sap_es26
from scgp_export.graphql.helper import sync_export_order_from_es26
import sap_migration.models as sap_migration_models


class AgencyInput(InputObjectType):
    order_type = graphene.Field(ScgExportOrderType, description="Order Type")
    sales_organization_id = graphene.ID(description="Sales Org")
    distribution_channel_id = graphene.ID(description="Distribution Channel")
    division_id = graphene.ID(description="Division")
    sales_office_id = graphene.ID(description="Sale office")
    sales_group_id = graphene.ID(description="Sales Group")


class ExportOrderHeaderUpdateInput(InputObjectType):
    ship_to = graphene.String(description="Ship To")
    bill_to = graphene.String(description="Bill To")
    po_date = graphene.Date(description="PO Date")
    po_no = graphene.String(description="PO Number")
    request_date = graphene.Date(description="Request Date")
    ref_pi_no = graphene.String(description="Ref. Pi No.")
    usage = graphene.String(description="Usage")
    unloading_point = graphene.String(description="Unloading Point")
    place_of_delivery = graphene.String(description="Place of Delivery")
    port_of_discharge = graphene.String(description="Port of Discharge")
    port_of_loading = graphene.String(description="Port of Loading")
    no_of_containers = graphene.String(description="No. of Containers")
    uom = graphene.String(description="UOM")
    gw_uom = graphene.String(description="G.W.UOM")
    etd = graphene.String(description="ETD")
    eta = graphene.String(description="ETA")
    dlc_expiry_date = graphene.Date(description="D-L/C : Expiry Date")
    dlc_no = graphene.String(description="D-L/C No.")
    dlc_latest_delivery_date = graphene.Date(description="D-L/C : Latest Delivery Date")
    description = graphene.String(description="Description")
    payer = graphene.String(description="Payer")
    end_customer = graphene.String(description="End Customer")
    payment_instruction = graphene.String(description="Payment Instruction")
    remark = graphene.String(description="Remark")
    production_information = graphene.String(description="Production information")
    internal_comment_to_warehouse = graphene.String(description="Internal Comments to Warehouse")
    incoterms_2 = graphene.String(description="Incoterms 2")
    shipping_mark = graphene.String(description="Shipping Mark")


class ExportOrderLineUpdateInput(InputObjectType):
    id = graphene.ID(description="ID of an order line to update.", required=True)

    # Tab A
    quantity = graphene.Float()
    quantity_unit = graphene.String()
    weight_unit = graphene.String()
    weight = graphene.Float()
    item_cat_eo = graphene.String()
    plant = graphene.String()
    ref_pi_no = graphene.String()
    request_date = graphene.Date()

    # Tab B
    route = graphene.String()
    delivery_tol_under = graphene.Float()
    delivery_tol_over = graphene.Float()
    delivery_tol_unlimited = graphene.Boolean()
    roll_diameter = graphene.String()
    roll_core_diameter = graphene.String()
    roll_quantity = graphene.String()
    roll_per_pallet = graphene.String()
    pallet_size = graphene.String()
    pallet_no = graphene.String()
    package_quantity = graphene.String()
    packing_list = graphene.String()
    shipping_point = graphene.String()
    remark = graphene.String()
    shipping_mark = graphene.String()
    reject_reason = graphene.Field(ScgExportRejectReason)


class ExportOrderLineInput(ExportOrderLineUpdateInput):
    id = graphene.ID()
    pi_product = graphene.ID()
    item_no = graphene.String()


class ExportOrderUpdateInput(InputObjectType):
    agency = graphene.Field(AgencyInput)
    order_header = graphene.Field(ExportOrderHeaderUpdateInput)
    status = graphene.Field(ScgpExportOrderStatus, default_value=ScgpExportOrderStatus.DRAFT.value, required=True)
    lines = graphene.List(
        ExportOrderLineInput,
        description="Fields to update order line"
    )


class ExportOrderLineDraftInput(InputObjectType):
    id = graphene.ID(description="ID of an order line to update.", required=True)
    quantity = graphene.Float()
    request_date = graphene.Date()


class ExportOrderUpdateDraftInput(InputObjectType):
    lines = graphene.List(
        ExportOrderLineDraftInput,
        description="Fields to update draft order line"
    )


class ExportOrderLineUpdateDraft(ModelMutation):
    order_lines = graphene.List(ExportOrderLine, description="Order lines")

    class Arguments:
        input = ExportOrderUpdateDraftInput(required=True, description="Fields required to update order line")

    class Meta:
        description = "Update order line"
        model = models.OrderLines
        object_type = graphene.Boolean
        return_field_name = "status"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def validate_input(cls, data):
        for line in data.get("input").get("lines", []):
            if line.get("quantity") and line.get("quantity") <= 0:
                raise ValidationError(
                    {
                        "quantity": ValidationError(
                            "The quantity must be greater than 0",
                            code=ScgpExportErrorCode.INVALID.value,
                        )
                    }
                )

    @classmethod
    def perform_mutation(cls, root, info, **data):
        cls.validate_input(data)
        order_lines = update_export_order_line_draft(data.get("input", {}).get("lines", []))
        resp = cls.success_response(True)
        resp.order_lines = order_lines
        return resp


class ExportOrderUpdate(ModelMutation):
    success = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessage)
    sap_item_messages = graphene.List(SapItemMessage)
    i_plan_messages = graphene.List(IPlanMessage)
    warning_messages = graphene.List(WarningMessage)

    class Arguments:
        id = graphene.ID(description="ID of an order to update.", required=True)
        input = ExportOrderUpdateInput(
            required=True, description="Fields required to update order"
        )

    class Meta:
        description = "Update export order"
        model = models.Order
        object_type = ExportOrderExtended
        return_field_name = "order"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def validate_input(cls, data):
        if data.get("input") and data.get("input").get("lines"):
            for line in data.get("input").get("lines"):
                if line.get("quantity") and line.get("quantity") <= 0:
                    raise ValidationError(
                        {
                            "quantity": ValidationError(
                                "The quantity must be greater than 0",
                                code=ScgpExportErrorCode.INVALID.value,
                            )
                        }
                    )
            # SEO-2598: Cancel due to new requirement
            # lst_plant = list(map(lambda item: item.get('plant'), data.get("input").get("lines")))
            # special_plants = ['754F', '7531', '7533']
            # if (
            #         validate_list_have_item_in(lst_plant, haystack=special_plants) and
            #         not validate_list_items_equal(lst_plant)
            # ):
            #     raise ValidationError(
            #         {
            #             "plant": ValidationError(
            #                 message=f"สำหรับ plant {', '.join(special_plants)} กรุณากรอกข้อมูล plant เดียวกันทุกรายการ",
            #                 code=ScgpExportErrorCode.INVALID.value
            #             )
            #         }
            #     )

        if data.get("input").get("status", None) != ScgpExportOrderStatus.CONFIRMED.value:
            return

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        cls.validate_input(data)
        user = info.context.user
        order_id = data.get("id")
        (
            result,
            success,
            sap_order_messages,
            sap_item_messages,
            i_plan_messages,
            warning_messages,
            is_validation_error,
            error_message
        ) = update_export_order(order_id, data.get("input"), user, info)
        if is_validation_error:
            logging.info(
                f"[Export create order] Time Taken to complete FE request: {time.time() - start_time} seconds,"
                f"is_validation_error : {is_validation_error}")
            raise error_message
        response = get_response_message(
            cls.success_response(result),
            success,
            sap_order_messages,
            sap_item_messages,
            i_plan_messages,
            warning_messages
        )
        diff_time = time.time() - start_time
        logging.info(f"[Export create order] Time Taken to complete FE request: {diff_time} seconds")
        if success:
            add_metric_process_order(
                settings.NEW_RELIC_CREATE_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.EXPORT,
                order_id=result.id
            )
        return response


class ExportOrderLineUpdate(ModelMutation):
    order = graphene.Field(ExportOrderExtended)

    class Arguments:
        order_id = graphene.ID(required=True)
        input = NonNullList(
            ExportOrderLineUpdateInput,
            required=True,
            description="Fields required to update order line"
        )

    class Meta:
        description = "Update export order line"
        model = models.OrderLines
        object_type = graphene.Boolean
        return_field_name = "status"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def validate_input(cls, input_data):
        for line in input_data:
            today = date.today()
            request_date = line.get("request_date")
            if request_date is not None and request_date <= today:
                raise ValidationError({
                    "request_date": ValidationError("Request date must be further than today",
                                                    code=ScgpExportErrorCode.INVALID.value)
                })

            if line.get("quantity") and line.get("quantity") <= 0:
                raise ValidationError(
                    {
                        "quantity": ValidationError(
                            "The quantity must be greater than 0",
                            code=ScgpExportErrorCode.INVALID.value,
                        )
                    }
                )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        input_data = data.get("input")
        order_id = data.get("order_id")
        cls.validate_input(input_data)
        user = info.context.user
        success, order = update_export_order_lines(order_id, input_data, user)
        response = cls.success_response(success)
        response.order = order
        return response


class ExportOrderHeaderCreateInput(InputObjectType):
    pi_id = graphene.ID(required=True)


class ExportOrderLineCreateInput(InputObjectType):
    pi_product = graphene.ID(required=True)
    quantity = graphene.Float(required=True)
    cart_item_id = graphene.ID(required=False)


class ChangeExportOrderLineAddProductInput(InputObjectType):
    pi_product = graphene.ID(required=True)
    quantity = graphene.Float(required=True)
    orderlines_id = graphene.List(graphene.ID, required=True)


class ExportOrderLineAddProductInput(InputObjectType):
    pi_product = graphene.ID(required=True)
    quantity = graphene.Float(required=True)


class ExportOrderCreateInput(InputObjectType):
    order_header = graphene.Field(ExportOrderHeaderCreateInput, required=True)
    lines = NonNullList(
        ExportOrderLineCreateInput,
        required=True
    )


class ExportOrderCreate(ModelMutation):
    class Arguments:
        input = ExportOrderCreateInput(
            required=True, description="Fields required to update order"
        )

    class Meta:
        description = "Create export order"
        model = models.Order
        object_type = ExportOrderExtended
        return_field_name = "order"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def validate_input(cls, input_data):
        for line in input_data.get("lines"):
            if line.get("quantity", 0) <= 0:
                raise ValidationError(
                    {
                        "quantity": ValidationError(
                            "The quantity must be greater than 0",
                            code=ScgpExportErrorCode.INVALID.value,
                        )
                    }
                )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        input_data = data.get("input")
        cls.validate_input(input_data)
        result = create_export_order(info, input_data)
        return cls.success_response(result)


class ExportOrderLinesDelete(ModelMutation):
    class Arguments:
        ids = graphene.List(
            graphene.ID, description="IDs of order line to delete."
        )
        delete_all = graphene.Boolean()
        order_id = graphene.ID()

    class Meta:
        description = "delete order line"
        model = models.OrderLines
        object_type = graphene.Boolean
        return_field_name = "status"
        error_type_class = ScgpExportError
        error_type_field = "scgp_customer_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = delete_export_order_lines(data.get("ids", []), data.get("delete_all", False),
                                           data.get("order_id", False), info.context.user)
        return cls.success_response(result)


class ExportOrderAddProducts(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of an order to update.", required=True)
        input = NonNullList(ExportOrderLineAddProductInput, required=True)

    class Meta:
        description = "add product to order"
        model = models.OrderLines
        object_type = ExportOrderExtended
        return_field_name = "order"
        error_type_class = ScgpExportError
        error_type_field = "scgp_customer_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def validate_input(cls, data):
        for line in data.get("input", []):
            validate_positive_decimal(line.get("quantity", 0))
            # validate_qty_over_remaining(line.get("quantity", 0), line.get("pi_product"))

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cls.validate_input(data)
        result = add_products_to_export_order(data.get("id"), data.get("input", []), info)
        return cls.success_response(result)


class ExportOrderLineUpdateAllInput(InputObjectType):
    request_date = graphene.Date(required=True)


class ExportOrderLineUpdateAll(ModelMutation):
    order = graphene.Field(ExportOrderExtended)

    class Arguments:
        id = graphene.ID(description="ID of an order to update.", required=True)
        input = ExportOrderLineUpdateAllInput(
            required=True, description="Fields required to update order line"
        )

    class Meta:
        description = "Update export order"
        model = models.Order
        object_type = graphene.Boolean
        return_field_name = "status"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def validate_input(cls, input_data):
        today = date.today()
        request_date = input_data.get("request_date")
        if request_date is not None and request_date <= today:
            raise ValidationError({
                "request_date": ValidationError("Request date must be further than today",
                                                code=ScgpExportErrorCode.INVALID.value)
            })

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        input_data = data.get("input")
        cls.validate_input(input_data)
        user = info.context.user
        success, order = update_all_export_order_lines(data.get("id"), input_data, user)
        response = cls.success_response(success)
        response.order = order
        return response


class InitialInput(InputObjectType):
    rejectReason = graphene.String()
    contractType = graphene.String()
    orderType = graphene.String()
    salesOrg = graphene.String()
    distributionChannel = graphene.String()
    division = graphene.String()
    contract = graphene.String()
    requestDeliveryDate = graphene.String()
    createAndChangeType = graphene.String()
    salesOffice = graphene.String()
    eoNo = graphene.String()
    changeType = graphene.String()
    lotNo = graphene.String()


class HeaderInput(InputObjectType):
    soldTo = graphene.String()
    shipTo = graphene.String()
    poNo = graphene.String()
    salesGroup = graphene.String()
    docCurrency = graphene.String()
    usage = graphene.String()
    unloadingPoint = graphene.String()
    incoterms = graphene.String()
    placeOfDelivery = graphene.String()
    paymentTerm = graphene.String()
    contactPerson = graphene.String()
    author = graphene.String()
    billTo = graphene.String()
    payer = graphene.String()
    salesEmployee = graphene.String()
    internalCommentToWarehouse = graphene.String()
    remark = graphene.String()
    paymentInstruction = graphene.String()
    portOfDischarge = graphene.String()
    noOfContainers = graphene.String()
    shippingMark = graphene.String()
    ETD = graphene.String()
    ETA = graphene.String()
    dlcNo = graphene.String()
    dlcExpiryDate = graphene.String()
    dlcLatestDeliveryDate = graphene.String()
    description = graphene.String()
    salesEmail = graphene.String()
    cc = graphene.String()
    endCustomer = graphene.String()
    productInfomation = graphene.String()
    uom = graphene.String()
    gwUom = graphene.String()


class ItemInput(InputObjectType):
    rejectReason = graphene.String()
    materialCode = graphene.String()
    orderQuantity = graphene.Float()
    unit = graphene.String()
    itemCatPi = graphene.String()
    itemCatEo = graphene.String()
    plant = graphene.String()
    conditionGroup1 = graphene.String()
    route = graphene.String()
    price = graphene.Float()
    priceCurrency = graphene.String()
    noOfRolls = graphene.Float()
    rollDiameterInch = graphene.String()
    rollCoreDiameterInch = graphene.String()
    remark = graphene.String()
    palletSize = graphene.String()
    reamRollPerPallet = graphene.Float()
    palletNo = graphene.String()
    noOfPackage = graphene.String()
    packingListText = graphene.String()
    commissionPercent = graphene.String()
    commission = graphene.String()
    commissionCurrency = graphene.String()
    eoItemNo = graphene.String()
    refPiStock = graphene.String()


class ReceiveEoData(ModelMutation):
    class Arguments:
        initial = InitialInput()
        header = HeaderInput()
        items = graphene.List(ItemInput)

    class Meta:
        description = "receive EO data"
        model = models.Order
        object_type = ExportOrderExtended
        return_field_name = "order"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"
        # permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        user = info.context.user
        result = sync_create_order_to_db(data, user)
        return cls.success_response(result)


class DuplicateOrder(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of a order to duplicate.", required=True)

    class Meta:
        description = "duplicate order"
        model = models.Order
        object_type = ExportOrderExtended
        return_field_name = "order"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order_id = data["id"]
        current_user = info.context.user
        new_order = duplicate_order(order_id, current_user)

        return cls.success_response(new_order)


class CallAPISapRoute(BaseMutation):
    response = graphene.Field(RouteType)

    class Arguments:
        pi_message_id = graphene.String(required=True, description="contract code of route")
        route = graphene.String(required=True, description="route of search input")
        route_description = graphene.String(required=True, description="description of route")
        max_records = graphene.Int(required=True, description="max record of route")

    class Meta:
        description = "call api sap route"
        object_type = RouteType
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        manager = info.context.plugins
        piMessageId = str(uuid.uuid1().int)
        body = {
            "piMessageId": piMessageId,
            "route": data["route"],
            "routeDescription": data["route_description"],
            "maxRecords": data["max_records"]
        }

        example_data = {
            "piMessageId": 5100000753,
            "status": "success",
            "reason": "Route download success, But There are more than 50 possible inputs",
            "routeList": [
                {
                    "route": 711001,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-กรุงเทพฯ โซนเหนือ"
                },
                {
                    "route": 711002,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-กรุงเทพฯ โซนตะวันออก"
                },
                {
                    "route": 711003,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-กรุงเทพฯ โซนกลาง"
                },
                {
                    "route": 711004,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-กรุงเทพฯ โซนใต้"
                },
                {
                    "route": 711005,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-กรุงเทพฯ โซนตะวันตก"
                },
                {
                    "route": 711006,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-กรุงเทพฯ บางขุนเทียน"
                },
                {
                    "route": 711100,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-นนทบุรี"
                },
                {
                    "route": 711101,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ปทุมธานี"
                },
                {
                    "route": 711102,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-อยุธยา"
                },
                {
                    "route": 711103,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-อ่างทอง"
                },
                {
                    "route": 711104,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ลพบุรี"
                },
                {
                    "route": 711105,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-สิงห์บุรี"
                },
                {
                    "route": 711106,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ชัยนาท"
                },
                {
                    "route": 711107,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-สระบุรี"
                },
                {
                    "route": 711108,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-สมุทรปราการ"
                },
                {
                    "route": 711109,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ชลบุรี"
                },
                {
                    "route": 711110,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ระยอง"
                },
                {
                    "route": 711111,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-จันทบุรี"
                },
                {
                    "route": 711112,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ตราด"
                },
                {
                    "route": 711113,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ฉะเชิงเทรา"
                },
                {
                    "route": 711114,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ปราจีนบุรี"
                },
                {
                    "route": 711115,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-นครนายก"
                },
                {
                    "route": 711116,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-สระแก้ว"
                },
                {
                    "route": 711117,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-นครราชสีมา"
                },
                {
                    "route": 711118,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-บุรีรัมย์"
                },
                {
                    "route": 711119,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-สุรินทร์"
                },
                {
                    "route": 711120,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ศรีสะเกษ"
                },
                {
                    "route": 711121,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-อุบลราชธานี"
                },
                {
                    "route": 711122,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ยโสธร"
                },
                {
                    "route": 711123,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ชัยภูมิ"
                },
                {
                    "route": 711124,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-อำนาจเจริญ"
                },
                {
                    "route": 711125,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-หนองบัวลำภู"
                },
                {
                    "route": 711126,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ขอนแก่น"
                },
                {
                    "route": 711127,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-อุดรธานี"
                },
                {
                    "route": 711128,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-เลย"
                },
                {
                    "route": 711129,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-หนองคาย"
                },
                {
                    "route": 711130,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-มหาสารคาม"
                },
                {
                    "route": 711131,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ร้อยเอ็ด"
                },
                {
                    "route": 711132,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-กาฬสินธุ์"
                },
                {
                    "route": 711133,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-สกลนคร"
                },
                {
                    "route": 711134,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-นครพนม"
                },
                {
                    "route": 711135,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-มุกดาหาร"
                },
                {
                    "route": 711136,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-เชียงใหม่"
                },
                {
                    "route": 711137,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ลำพูน"
                },
                {
                    "route": 711138,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-ลำปาง"
                },
                {
                    "route": 711139,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-อุตรดิตถ์"
                },
                {
                    "route": 711140,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-แพร่"
                },
                {
                    "route": 711141,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-น่าน"
                },
                {
                    "route": 711142,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-พะเยา"
                },
                {
                    "route": 711143,
                    "routeDescription": "กาญจนบุรี(วังศาลา)-เชียงราย"
                }
            ]
        }

        response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_get(
            SapEnpoint.ES_29.value,
            body
        )
        return cls(
            response=response
        )


class ExportOrderReasonForRejectInput(graphene.InputObjectType):
    reason_for_reject = graphene.Field(ChangeExportRejectReason)


class CancelExportOrder(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of a order to Cancel.", required=True)

    class Meta:
        description = "Cancel order"
        model = models.Order
        object_type = ExportOrderExtended
        return_field_name = "order"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        result = cancel_export_order(data["id"])
        return cls.success_response(result)


class CancelDeleteExportOrder(BaseMutation):
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    sap_order_messages = graphene.List(SapOrderMessage, default_value=[])
    sap_item_messages = graphene.List(SapItemMessage, default_value=[])

    class Arguments:
        so_no = graphene.String()
        item_nos = graphene.List(graphene.String, description="List of order line to cancel/delete")
        reason = ExportOrderReasonForRejectInput(required=True)

    class Meta:
        description = "cancel/delete order line"
        return_field_name = "order_lines"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        start_time = time.time()
        i_plan_messages, sap_order_messages, sap_item_messages = cancel_delete_export_order(data, info)
        diff_time = time.time() - start_time
        logging.info(f"[Export: Cancel/Delete] Time Taken to complete FE request: {diff_time} seconds")
        so_no = data.get("so_no")
        order = models.Order.objects.filter(so_no=so_no).first()
        if order and not (i_plan_messages or sap_order_messages or sap_item_messages):
            for api_name in ["ES14", "ES15"]:
                force_update_attributes("function", api_name, {"orderId": order.id})
            add_metric_process_order(
                settings.NEW_RELIC_CHANGE_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.EXPORT,
                order_id=order.id
            )
        return CancelDeleteExportOrder(
            i_plan_messages=i_plan_messages,
            sap_order_messages=sap_order_messages,
            sap_item_messages=sap_item_messages,
        )


class DownloadPDFOrder(BaseMutation):
    exported_file_base_64 = graphene.String()
    file_name = graphene.String()

    class Arguments:
        order_id = graphene.ID()
        so_no = graphene.String()
        sort_type = graphene.String()

    class Meta:
        description = "Download PDF order"
        return_field_name = "PDF"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        # Get data and print pdf from SAP
        so_no = data.get("so_no", None)
        if so_no:
            data["order_id"] = so_no
        sort_type = data.get("sort_type", "ASC")
        file_name, base64_string = download_pdf_change_order(data["order_id"], sort_type, info.context.user)
        return cls(exported_file_base_64=base64_string, file_name=file_name)


class CopyOrder(BaseMutation):
    new_order_id = graphene.ID()

    class Arguments:
        order_id = graphene.ID()

    class Meta:
        description = "Make a copy of an order"
        return_field_name = "order"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        order = clone_order(data["order_id"], info.context.user.id)
        return cls(new_order_id=order.id)


class ChangeParameterOfExport(ModelMutation):
    class Arguments:
        order_line_id = graphene.ID(required=True)

    class Meta:
        description = "change parameter of export"
        object_type = ChangeParameterIPlanType
        model = models.OrderLines
        return_field_name = "drop_down_list"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order_line_id = data["order_line_id"]
        result = change_parameter_of_export(order_line_id)
        return cls.success_response(result)


class UpdateInquiryMethodExportInput(InputObjectType):
    inquiry_method = graphene.Field(InquiryMethodType, required=True, default_value=InquiryMethodType.EXPORT.value)


class UpdateInquiryMethodExport(ModelMutation):
    class Arguments:
        order_line_id = graphene.ID(required=True)
        input = UpdateInquiryMethodExportInput(
            required=True, description="Fields required to update order line"
        )

    class Meta:
        description = "Update inquiry method of export"
        object_type = ExportOrderLine
        model = models.OrderLines
        return_field_name = "orderLine"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order_line_id = data["order_line_id"]
        inquiry_method = data["input"]["inquiry_method"]
        result = update_inquiry_method_export(order_line_id, inquiry_method)
        return cls.success_response(result)


class ExportAddProductToOrder(BaseMutation):
    result = graphene.List(ExportOrderLine)

    class Arguments:
        id = graphene.ID(description="ID of an order to update.", required=True)
        input = NonNullList(ChangeExportOrderLineAddProductInput, required=True)

    class Meta:
        description = "add product to order"
        return_field_name = "orderLine"
        error_type_class = ScgpExportError
        error_type_field = "scgp_customer_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def validate_input(cls, data):
        for line in data.get("input", []):
            validate_positive_decimal(line.get("quantity", 0))

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cls.validate_input(data)
        result = add_product_to_order(data.get("id"), data.get("input", []), info.context.user)
        return cls(result=result)


class UndoOrderLinesExport(BaseMutation):
    success = graphene.Boolean()
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    sap_item_messages = graphene.List(SapItemMessage, default_value=[])
    sap_order_messages = graphene.List(SapOrderMessage, default_value=[])

    class Arguments:
        so_no = graphene.String(required=True)
        item_no = graphene.List(graphene.String, required=True)

    class Meta:
        description = "Undo Order Lines Export"
        error_type_class = ScgpExportError
        error_type_field = "scgp_export_error"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        (
            success,
            i_plan_messages_response,
            sap_order_messages_response,
            sap_item_messages
        ) = undo_order_lines_export(data, info)
        so_no = data["so_no"]
        order = models.Order.objects.filter(so_no=so_no).first()
        diff_time = time.time() - start_time
        logging.info(f"[Export: Undo order lines] Time Taken to complete FE request: {diff_time} seconds")
        if success and order:
            # optional
            for api_name in ["ES14", "ES15"]:
                force_update_attributes("function", api_name, {"orderId": order.id})
            add_metric_process_order(
                settings.NEW_RELIC_CHANGE_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.EXPORT,
                order_id=order.id
            )
        return cls(success=success, i_plan_messages=i_plan_messages_response,
                   sap_order_messages=sap_order_messages_response, sap_item_messages=sap_item_messages)


class ExportOrderHeaderFixedDataInput(InputObjectType):
    pi_no = graphene.String(description="PI No", required=True)
    eo_no = graphene.String(description="EO No", required=True)
    sold_to = graphene.String(description="Sold to", required=True)
    bill_to = graphene.String(description="Bill to", required=True)
    ship_to = graphene.String(description="Ship to", required=True)


class ExportAddNewItemsInput(ExportOrderLineUpdateInput):
    id = graphene.ID()
    material_code = graphene.String(required=True, description="Material code")
    item_no = graphene.String(required=True, description="Item no")
    inquiry_method = graphene.String()


class ExportAddNewOrderLineInput(InputObjectType):
    order_header = graphene.Field(ExportOrderHeaderFixedDataInput, description="Fields to update order header",
                                  required=True)
    line = graphene.List(ExportAddNewItemsInput, description="Fields to update order line", required=True)


class ExportChangeOrderAddNewOrderLine(BaseMutation):
    success = graphene.Boolean()
    i_plan_messages = graphene.List(IPlanMessage, default_value=[])
    sap_order_messages = graphene.List(SapOrderMessage, default_value=[])
    sap_item_messages = graphene.List(SapItemMessage, default_value=[])
    order_lines = graphene.List(ExportOrderLine, default_value=[])

    class Arguments:
        id = graphene.ID(description="ID of an order to update.", required=True)
        input = ExportAddNewOrderLineInput(required=True)

    class Meta:
        description = "Export add new order line"
        error_type_class = ScgpExportError
        error_type_field = "checkout_errors"

    @classmethod
    def validate(cls, data):
        for order_line in data["line"]:
            order_line.update({"route": (order_line.get("route", "") or "").split("-")[0].strip(" ")})

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        input = data.get("input", {})
        cls.validate(input)
        i_plan_messages_response = []
        sap_order_messages_response = []
        sap_item_messages_response = []
        manager = get_plugins_manager()
        order_header = input.get("order_header", {})
        lines = sorted(input.get("line", []), key=lambda x: float(x['item_no']))
        logging.info(f"[Export: change order Add new items] For order {data.get('id','')} FE request: {data},"
                     f"by User:{info.context.user}")
        i_plan_request_remapping = {}
        success = True

        list_new_items_iplan, list_special_items = split_lines(lines)
        logging.info(f"[Export: change order Add new items] New items : {list_new_items_iplan},"
                     f" special_plant_items or container_items: {list_special_items}")
        update_plant_for_container_line_input(list_special_items, order_header["eo_no"])

        if list_new_items_iplan:
            logging.info("[Export: change order Add new items] calling... Iplan")
            response_i_plan_request = change_order_add_new_items_iplan_request(order_header, list_new_items_iplan,
                                                                               manager)
            logging.info("[Export: change order Add new items] called Iplan")
            i_plan_request_remapping, lines = handle_case_iplan_return_split_order(
                iplan_request_response=response_i_plan_request, list_new_items=list_new_items_iplan, lines=lines)
            is_iplan_full_success, i_plan_error_messages = get_iplan_error_messages(response_i_plan_request)
            logging.info(f"[Export: change order Add new items] is_iplan_fully_success: {is_iplan_full_success},"
                         f"i_plan_error_messages: {i_plan_error_messages}")
            if i_plan_error_messages:
                success = False
                i_plan_messages_response = i_plan_error_messages
                if len(i_plan_error_messages) != len(list_new_items_iplan):
                    rollback_items = [new_item for new_item in list_new_items_iplan if not any(
                        new_item["item_no"] == error_item["item_no"] for error_item in i_plan_error_messages)]
                    logging.info("[Export: change order Add new items] Calling Iplan_roll_back")
                    call_i_plan_rollback(manager, order_header, rollback_items)
                    logging.info("[Export: change order Add new items] Called Iplan_roll_back")
                logging.info(
                    f"[Export: change order Add new items] Time Taken to complete FE request: {time.time() - start_time} seconds")
                return cls(success=success, i_plan_messages=i_plan_messages_response,
                           sap_order_messages=sap_order_messages_response, sap_item_messages=sap_item_messages_response)
            data_for_es21 = add_special_order_line_to_iplan_data_for_call_es21(list_special_items,
                                                                               i_plan_request_remapping)
        else:
            default_data = {
                "failure": [],
                "header_code": order_header["eo_no"].lstrip("0"),
            }
            data_for_es21 = add_special_order_line_to_iplan_data_for_call_es21(list_special_items, default_data)
        list_new_items_iplan, list_special_items = split_lines(lines)
        lines = save_original_request_date(lines)
        logging.info("[Export: change order Add new items] Calling ES21")
        response_es21 = change_order_add_new_item_es_21(order_header, lines, data_for_es21,
                                                        manager)
        logging.info("[Export: change order Add new items] Called ES21")

        (
            sap_order_messages_response,
            sap_item_messages_response,
            is_being_process,
            is_es21_success
        ) = get_error_messages_from_sap_response_for_change_order(response_es21)

        logging.info(f"[Export: change order Add new items] is_ES21_success: {is_es21_success},"
                     f" sap_order_error_messages :{sap_order_messages_response}, "
                     f"sap_item_error_messages: {sap_item_messages_response}"
                     )
        if not is_es21_success:
            success = False
            logging.info("[Export: change order Add new items] calling i_plan_roll_back as ES21 failed")
            call_i_plan_rollback(manager, order_header, list_new_items_iplan)
            logging.info("[Export: change order Add new items] i_plan_roll_back called")
            logging.info(
                f"[Export: change order Add new items] Time Taken to complete FE request: {time.time() - start_time} seconds")
            return cls(success=success, i_plan_messages=i_plan_messages_response,
                       sap_order_messages=sap_order_messages_response, sap_item_messages=sap_item_messages_response)
        es21_remapping = remapping_es21(response_es21)
        order_lines = sync_order_line_add_new_items(list_new_items_iplan, order_header, i_plan_request_remapping,
                                      es21_remapping, info, lines)
        _order = order_lines and order_lines[0].order or None
        if list_new_items_iplan:
            try:
                logging.info("[Export: change order Add new items] calling i_plan_confirm")
                response_i_plan_confirm = change_order_add_new_item_i_plan_confirm(response_i_plan_request,
                                                                                   order_header,
                                                                                   list_new_items_iplan,
                                                                                   es21_remapping,
                                                                                   manager,
                                                                                   order=_order)
                logging.info("[Export: change order Add new items] i_plan_confirm called")
                is_iplan_full_success, i_plan_error_messages = get_iplan_error_messages(response_i_plan_confirm)
                logging.info(f"[Export: change order Add new items] is_iplan_confirm_full_success: {is_iplan_full_success},"
                             f"i_plan_confirm_error_messages: {i_plan_error_messages}")
                if i_plan_error_messages:
                    success = False
                    i_plan_messages_response = i_plan_error_messages
                    error_order_lines = get_error_order_lines_from_iplan_response(order_lines, response_i_plan_confirm)
                    update_attention_type_r5(error_order_lines)
                    logging.info(
                        f"[Export: change order Add new items] Time Taken to complete FE request: {time.time() - start_time} seconds")
                    return cls(success=success, i_plan_messages=i_plan_messages_response,
                               sap_order_messages=sap_order_messages_response,
                               sap_item_messages=sap_item_messages_response)
            except Exception as e:
                logging.exception(
                    "[Export: change order Add new items] YT65156/confirm API failed with exception:" + str(e))
                success = False
                i_plan_messages_response.append({"message": e.messages[0]})
                update_attention_type_r5(order_lines)
                logging.info(
                    f"[Export: change order Add new items] Time Taken to complete FE request: {time.time() - start_time} seconds")
                return cls(success=success, i_plan_messages=i_plan_messages_response,
                           sap_order_messages=sap_order_messages_response, sap_item_messages=sap_item_messages_response)
        logging.info(
            f"[Export: change order Add new items] Time Taken to complete FE request: {time.time() - start_time} seconds")
        diff_time = time.time() - start_time
        if success and _order:
            # optional
            for api_name in ["ES14", "ES15"]:
                force_update_attributes("function", api_name, {"orderId": _order.id})
            add_metric_process_order(
                settings.NEW_RELIC_CHANGE_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.EXPORT,
                order_id=_order.id
            )
        return cls(success=success, i_plan_messages=i_plan_messages_response,
                   sap_order_messages=sap_order_messages_response, sap_item_messages=sap_item_messages_response)


class DeleteExportOrderLineDraft(BaseMutation):
    success = graphene.Boolean()

    class Arguments:
        id = graphene.ID(required=True, description="ID of the order line to delete.")

    class Meta:
        description = "Delete an order line."
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)
        error_type_class = ScgpExportError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order_line_id = data.get("id")
        order_lines = models.OrderLines.all_objects.filter(id=order_line_id)
        if order_lines:
            order_id = order_lines[0].order_id
            order_lines.delete()
            lines = models.OrderLines.all_objects.filter(order_id=order_id)
            if not lines:
                sap_migration_models.Order.objects.filter(id=order_id).update(
                    product_group=None
                )
        return cls(success=True)
