import uuid
from copy import deepcopy
from datetime import date, datetime

from django.core.exceptions import ValidationError

from common.enum import MulesoftServiceType
from common.helpers import getattrd
from common.mulesoft_api import MulesoftApiRequest
from sap_master_data import models as master_models
from sap_migration import models as sap_migration_models
from sap_migration.graphql.enums import OrderType
from scg_checkout.error_codes import ContractCheckoutErrorCode
from scg_checkout.graphql.enums import (
    AtpCtpStatus,
    IPLanConfirmStatus,
    IPlanOrderItemStatus,
    IPLanResponseStatus,
    IPlanTypeOfDelivery,
    IPlanUpdateItemTime,
    IPlanUpdateOrderStatus,
    MaterialType,
    ProductionStatus,
    SapUpdateFlag,
    ScgOrderStatus,
)
from scg_checkout.graphql.helper import (
    prepare_param_es21_order_text_for_change_order_domestic,
)
from scg_checkout.graphql.implementations.iplan import (
    change_parameter_follow_inquiry_method,
    get_contract_consignment_location_from_order,
    get_contract_no_from_order,
    get_ship_to_country_from_order,
    get_shipping_remark_from_order,
    get_sold_to_name_es14_partneraddress_from_order,
    update_plant_for_container_order_lines,
)
from scg_checkout.graphql.implementations.sap import (
    date_to_sap_date,
    get_order_partner_for_es21,
)
from scgp_eo_upload.implementations.helpers import (
    eo_upload_send_email_when_call_api_fail,
)
from scgp_export.graphql.enums import IPlanEndPoint, ItemCat, SapEnpoint, TextID
from scgp_export.graphql.helper import (
    _is_updated,
    _update_base,
    handle_request_text_to_es21,
)
from scgp_po_upload.graphql.enums import SAP21, IPlanAcknowledge
from scgp_require_attention_items.graphql.helper import update_attention_type_r5

# XXX: iPlan want to make it shorter (temp order number)
LEN_OF_HEADER_CODE = 12


def update_remark_order_line(order_line_remark, remark):
    if not order_line_remark:
        return remark
    if remark not in order_line_remark:
        return ", ".join(
            sorted(
                map(lambda x: x.strip(), f"{order_line_remark}, {remark}".split(","))
            )
        )
    return order_line_remark


def has_special_plant(order_line):
    # SEO-3361
    if order_line.plant in ["754F", "7531", "7533"]:
        return True
    return False


def check_recall_i_plan(
    order,
    origin_order_lines,
    updated_order_lines,
    sap_update_flag,
    accept_confirm_date=False,
):
    """
    Validation updatable field
    and compare original order lines vs updated order line
    to check re-call i-plan
    @param order: order object
    @param origin_order_lines: list order line before update
    @param updated_order_lines: list order line after update
    @param sap_update_flag: status to call SAP for each item
    @return: dict: {
        update_attention_r1_items: Item need update attention
        i_plan_update_items: Item need call i-plan to update
    }
    """
    order_status = order.status
    order_status_rank = ScgOrderStatus.STATUS_RANK.value
    if order_status in order_status_rank and order_status_rank.index(
        order_status
    ) == order_status_rank.index(ScgOrderStatus.COMPLETED_ORDER.value):
        raise ValidationError(
            {
                "order": ValidationError(
                    "Cannot update the completed order.",
                    code=ContractCheckoutErrorCode.NOT_FOUND.value,
                )
            }
        )

    dict_origin_order_lines = {}
    for ol in origin_order_lines:
        dict_origin_order_lines[ol.item_no] = ol

    production_status_rank = ProductionStatus.STATUS_RANK.value
    item_status_rank = IPlanOrderItemStatus.IPLAN_ORDER_LINE_RANK.value
    new_items = []
    delete_items = []
    update_items = []

    update_attention_r1_items = []

    i_plan_update_items = {
        IPlanUpdateItemTime.BEFORE_PRODUCTION.value: [],
        IPlanUpdateItemTime.DURING_PRODUCTION.value: [],
        IPlanUpdateItemTime.AFTER_PRODUCTION.value: [],
    }

    for updated_line in updated_order_lines:
        if sap_update_flag.get(updated_line.item_no, "") == SapUpdateFlag.INSERT.value:
            # Case create new item
            new_items.append(updated_line)
            continue
        if sap_update_flag.get(updated_line.item_no, "") == SapUpdateFlag.DELETE.value:
            # Case delete item
            delete_items.append(updated_line)
            continue
        if sap_update_flag.get(updated_line.item_no, "") == SapUpdateFlag.UPDATE.value:
            # Case update item
            update_items.append(updated_line)
        production_status = updated_line.production_status
        origin_line = dict_origin_order_lines.get(updated_line.item_no)

        is_line_updated = False
        es27_updatable_field = [
            "quantity",
            "request_date",
            "plant",
        ]
        for attr in es27_updatable_field:
            if (
                getattr(updated_line, attr) != getattr(origin_line, attr)
                or accept_confirm_date
            ):
                is_line_updated = True

        # Only call iplan if order line was updated and has NOT special plant(SEO-3361)
        if not (is_line_updated and not has_special_plant(updated_line)):
            continue

        if accept_confirm_date:
            updated_line.request_date = origin_line.confirmed_date
        # If item status is complete => raise error
        # If item status >= partial delivery => not allow change plant, qty, request date
        item_status = updated_line.item_status_en
        if item_status == IPlanOrderItemStatus.COMPLETE_DELIVERY.value:
            raise ValidationError(
                {
                    "order_item": ValidationError(
                        "Cannot update the Completed Delivery item.",
                        code=ContractCheckoutErrorCode.NOT_FOUND.value,
                    )
                }
            )

        if item_status in item_status_rank and item_status_rank.index(
            item_status
        ) >= item_status_rank.index(IPlanOrderItemStatus.PARTIAL_DELIVERY.value):
            if (
                origin_line.request_date != updated_line.request_date
                or origin_line.quantity != updated_line.quantity
                or origin_line.plant != updated_line.plant
            ):
                raise ValidationError(
                    {
                        "order_item": ValidationError(
                            "Cannot update the Partial Delivery item.",
                            code=ContractCheckoutErrorCode.NOT_FOUND.value,
                        )
                    }
                )

        # Check i-plan is ATP or CTP
        # If ‘ATP': On hand stock = 'True’ AND All operation fields is Blank field
        # If ‘ATP Future': On hand stock = 'False’ AND All operation fields is blank field
        # If ‘CTP': On hand stock = 'False’ AND one of operation fields is not blank field
        is_ctp_status = False
        if not updated_line.i_plan_on_hand_stock and updated_line.i_plan_operations:
            is_ctp_status = True

        if not is_ctp_status:
            i_plan_update_items[IPlanUpdateItemTime.BEFORE_PRODUCTION.value].append(
                updated_line
            )
            continue

        if production_status in production_status_rank:
            if production_status_rank.index(
                production_status
            ) < production_status_rank.index(ProductionStatus.CLOSE_RUN.value):
                # Scenario 1
                # Change item before production [Production Status < Close Run]
                # Plant [Allow to change]
                # Request Delivery Date  [Allow to change]
                # Order QTY [Allow to change]
                # Call i-plan for new solution
                if (
                    origin_line.request_date != updated_line.request_date
                    or origin_line.quantity != updated_line.quantity
                    or origin_line.plant != updated_line.plant
                ):
                    i_plan_update_items[
                        IPlanUpdateItemTime.BEFORE_PRODUCTION.value
                    ].append(updated_line)
            elif production_status_rank.index(
                production_status
            ) < production_status_rank.index(ProductionStatus.COMPLETED.value):
                # Scenario 2
                # Change item during production [Production Status < Completed]
                # Plant [Not Allow to change]
                # Request Delivery Date [Allow to change]
                # Order QTY [Allow to decrease]
                if origin_line.plant != updated_line.plant:
                    raise ValidationError(
                        {
                            "plant": ValidationError(
                                "Cannot update plant for this order",
                                code=ContractCheckoutErrorCode.NOT_FOUND.value,
                            )
                        }
                    )

                if origin_line.quantity < updated_line.quantity:
                    raise ValidationError(
                        {
                            "quantity": ValidationError(
                                "Cannot increase quantity for this order",
                                code=ContractCheckoutErrorCode.NOT_FOUND.value,
                            )
                        }
                    )

                if (
                    origin_line.request_date != updated_line.request_date
                    or origin_line.quantity != updated_line.quantity
                ):
                    if updated_line.request_date < updated_line.confirmed_date:
                        update_attention_r1_items.append(updated_line)
                    i_plan_update_items[
                        IPlanUpdateItemTime.DURING_PRODUCTION.value
                    ].append(updated_line)
            elif production_status_rank.index(
                production_status
            ) == production_status_rank.index(ProductionStatus.COMPLETED.value):
                # Scenario 3
                # Change item after production [Production Status = Completed]
                # Plant [Not Allow to change]
                # Request Delivery Date [Allow to change if after confirm date]
                # Order QTY [Allow to decrease]
                if origin_line.plant != updated_line.plant:
                    raise ValidationError(
                        {
                            "plant": ValidationError(
                                "Cannot update plant for this order",
                                code=ContractCheckoutErrorCode.NOT_FOUND.value,
                            )
                        }
                    )

                if origin_line.quantity < updated_line.quantity:
                    raise ValidationError(
                        {
                            "quantity": ValidationError(
                                "Cannot increase quantity for this order",
                                code=ContractCheckoutErrorCode.NOT_FOUND.value,
                            )
                        }
                    )

                if origin_line.confirmed_date < updated_line.request_date:
                    raise ValidationError(
                        {
                            "request_date": ValidationError(
                                "Cannot update request date before confirmed date for this order",
                                code=ContractCheckoutErrorCode.NOT_FOUND.value,
                            )
                        }
                    )

                if (
                    origin_line.request_date != updated_line.request_date
                    or origin_line.quantity != updated_line.quantity
                ):
                    i_plan_update_items[
                        IPlanUpdateItemTime.AFTER_PRODUCTION.value
                    ].append(updated_line)
        elif (
            origin_line.request_date != updated_line.request_date
            or origin_line.quantity != updated_line.quantity
            or origin_line.plant != updated_line.plant
        ):
            # Case production status is None or not in production_status_rank anhht
            i_plan_update_items[IPlanUpdateItemTime.BEFORE_PRODUCTION.value].append(
                updated_line
            )
    return {
        "update_attention_r1_items": update_attention_r1_items,
        "i_plan_update_items": i_plan_update_items,
        "new_items": new_items,
        "delete_items": delete_items,
        "update_items": update_items,
    }


def update_confirm_qty_after_call_iplan(dict_order_lines, i_plan_order_lines):
    e_ordering_iplan_lines = []
    for iplan_line in i_plan_order_lines:
        line_num_int = str(int(float(iplan_line["lineNumber"])))
        if f"{line_num_int}.001" == iplan_line["lineNumber"]:
            e_ordering_order_line = dict_order_lines.get(line_num_int)
            if e_ordering_order_line:
                e_ordering_iplan_line = e_ordering_order_line.iplan
                e_ordering_iplan_line.iplant_confirm_quantity = iplan_line.get(
                    "quantity", 0
                )
                e_ordering_iplan_lines.append(e_ordering_iplan_line)
    if e_ordering_iplan_lines:
        sap_migration_models.OrderLineIPlan.objects.bulk_update(
            e_ordering_iplan_lines, ["iplant_confirm_quantity"]
        )


def recall_i_plan_atp_ctp(
    order,
    update_items,
    manager,
    accept_confirm_date=False,
    call_type=None,
    sap_update_flag=None,
    original_order=None,
    original_order_lines=None,
    pre_update_lines=None,
    export_delete_flag=True,
    updated_items=None,
    require_attention=False,
):
    """
    Re-call i-plan to get new solution
    and call SAP to update order when i-plan response new solution
    @param order:
    @param update_items:
    @param manager:
    @param sap_update_flag:
    @param call_type: use for send mail from eo upload feature
    @return:
    """
    pre_update_lines = pre_update_lines or {}
    updated_items = updated_items or []
    success = True
    sap_order_messages = []
    sap_item_messages = []
    i_plan_messages = []
    order_lines_iplan = []
    dummy_order = "false"

    qs_order_lines = sap_migration_models.OrderLines.objects.filter(order=order)
    dict_order_lines = {}
    container_order_lines = []
    for line in qs_order_lines:
        dict_order_lines[line.item_no] = line
        # [SEO-3929] Not call Iplan with special plant
        if line.item_cat_eo != ItemCat.ZKC0.value and not has_special_plant(line):
            order_lines_iplan.append(line)
        else:
            container_order_lines.append(line)
    if call_type == "eo_upload":
        order_lines_iplan = filter_no_outsource_order_lines(order_lines_iplan)

    i_plan_response = request_i_plan_to_get_new_solution(  # TODO
        order,
        update_items,
        manager,
        dummy_order,
        order_lines_iplan,
        require_attention,
    )
    i_plan_response_header = i_plan_response.get("DDQResponse").get("DDQResponseHeader")

    if len(i_plan_response_header):
        i_plan_order = i_plan_response_header[0]
        i_plan_order_lines = i_plan_order.get("DDQResponseLine")
        for i_plan_line in i_plan_order_lines:
            if (
                i_plan_line.get("returnStatus", "").lower()
                == IPLanResponseStatus.FAILURE.value.lower()
            ):
                success = False
                return_code = i_plan_line.get("returnCode")
                if return_code:
                    i_plan_messages.append(
                        {
                            "item_no": i_plan_line.get("lineNumber"),
                            "first_code": return_code[24:32],
                            "second_code": return_code[18:24],
                            "message": i_plan_line.get("returnCodeDescription"),
                        }
                    )
                else:
                    i_plan_messages.append(
                        {
                            "item_no": i_plan_line.get("lineNumber"),
                            "first_code": "0",
                            "second_code": "0",
                            "message": "",
                        }
                    )

        # update plant for container order lines
        update_plant_for_container_order_lines(container_order_lines, qs_order_lines)

        if not success:
            if any(
                line.get("returnStatus").lower()
                == IPLanResponseStatus.FAILURE.value.lower()
                for line in i_plan_order_lines
            ):
                header_code = i_plan_response_header[0].get("headerCode")
                _rollback_success_items_if_request_fail(
                    manager,
                    i_plan_order_lines,
                    header_code,
                    IPLanConfirmStatus.ROLLBACK.value,
                )
            if call_type == "eo_upload":
                eo_upload_send_email_when_call_api_fail(
                    manager, order, "Update", "IPlan", i_plan_response, "iplan_request"
                )
        else:
            # If SAP success, update i-plan operation to order line, update atc_ctp status to order line i_plan
            e_ordering_order_lines = []
            e_ordering_order_lines_i_plan = []
            for i_plan_line in i_plan_order_lines:
                line_id = i_plan_line.get("lineNumber")
                e_ordering_order_line = dict_order_lines.get(line_id)
                if not e_ordering_order_line:
                    continue

                i_plan_on_hand_stock = i_plan_line.get("onHandStock")
                i_plan_operations = i_plan_line.get("DDQResponseOperation") or None

                # Update order line i-plan table
                e_ordering_order_line_i_plan = e_ordering_order_line.iplan
                atp_ctp_status = None
                if i_plan_on_hand_stock is True and not i_plan_operations:
                    atp_ctp_status = AtpCtpStatus.ATP.value
                elif i_plan_on_hand_stock is False and not i_plan_operations:
                    atp_ctp_status = AtpCtpStatus.ATP_FUTURE.value
                elif i_plan_on_hand_stock is False and i_plan_operations:
                    atp_ctp_status = AtpCtpStatus.CTP.value

                if not e_ordering_order_line_i_plan:
                    e_ordering_order_line_i_plan = (
                        sap_migration_models.OrderLineIPlan.objects.create(
                            atp_ctp=atp_ctp_status
                        )
                    )
                    e_ordering_order_line.iplan = e_ordering_order_line_i_plan
                else:
                    e_ordering_order_line_i_plan.atp_ctp_detail = atp_ctp_status
                    e_ordering_order_lines_i_plan.append(e_ordering_order_line_i_plan)

                # Update order line table
                e_ordering_order_line.i_plan_on_hand_stock = i_plan_on_hand_stock
                e_ordering_order_line.i_plan_operations = i_plan_operations
                # save return status for mock confirmed date
                e_ordering_order_line.return_status = i_plan_line.get("status", "")
                e_ordering_order_lines.append(e_ordering_order_line)

            sap_migration_models.OrderLines.objects.bulk_update(
                e_ordering_order_lines,
                fields=[
                    "i_plan_on_hand_stock",
                    "i_plan_operations",
                    "iplan",
                    "return_status",
                ],
            )

            if len(e_ordering_order_lines_i_plan):
                sap_migration_models.OrderLineIPlan.objects.bulk_update(
                    e_ordering_order_lines_i_plan,
                    fields=[
                        "atp_ctp",
                    ],
                )
            update_confirm_qty_after_call_iplan(dict_order_lines, i_plan_order_lines)
            # Call sap to update
            (
                sap_response_success,
                sap_order_messages,
                sap_item_messages,
            ) = sap_update_order(
                order,
                manager,
                sap_update_flag=sap_update_flag,
                original_order=original_order,
                origin_order_lines=original_order_lines,
                updated_data=original_order,
                pre_update_lines=pre_update_lines,
                export_delete_flag=export_delete_flag,
                updated_items=updated_items,
                accept_confirm_date=accept_confirm_date,
            )
            sap_order_number = order.so_no
            if sap_response_success:
                # Call i-plan confirm item when sap update order successfully
                i_plan_acknowledge = confirm_i_plan(
                    i_plan_response=i_plan_response,
                    status=IPLanConfirmStatus.COMMIT.value,
                    manager=manager,
                    sap_order_number=sap_order_number,
                    order=order,
                    require_attention=require_attention,
                )
                i_plan_acknowledge_headers = i_plan_acknowledge.get(
                    "DDQAcknowledge"
                ).get("DDQAcknowledgeHeader")

                # Check commit i-plan success or not to update R5 flag for e-ordering line
                update_attention_r5_items = []
                if len(i_plan_acknowledge_headers):
                    i_plan_acknowledge_header = i_plan_acknowledge_headers[0]
                    i_plan_acknowledge_line = i_plan_acknowledge_header.get(
                        "DDQAcknowledgeLine"
                    )

                    confirm_success_line_ids = []
                    for acknowledge_line in i_plan_acknowledge_line:
                        so_no = i_plan_acknowledge_header.get("headerCode").zfill(10)
                        if (
                            acknowledge_line.get("returnStatus").lower()
                            == IPlanAcknowledge.SUCCESS.value
                        ):
                            item = sap_migration_models.OrderLines.objects.filter(
                                order__so_no=so_no,
                                item_no=acknowledge_line.get("lineNumber"),
                            ).first()
                            confirm_success_line_ids.append(item.id)

                    for update_item in update_items:
                        if update_item.id not in confirm_success_line_ids:
                            update_attention_r5_items.append(update_item)

                if len(update_attention_r5_items):
                    update_attention_type_r5(update_attention_r5_items)
            else:
                success = False
                # Call i-plan rollback item when sap failed to create order
                confirm_i_plan(
                    i_plan_response=i_plan_response,
                    status=IPLanConfirmStatus.ROLLBACK.value,
                    manager=manager,
                    sap_order_number=sap_order_number,
                    order=order,
                )
    else:
        success = False

    return {
        "success": success,
        "i_plan_response": i_plan_response,
        "sap_order_messages": sap_order_messages,
        "sap_item_messages": sap_item_messages,
        "i_plan_messages": i_plan_messages,
    }


def request_i_plan_to_get_new_solution(
    order,
    update_items,
    manager,
    is_dummy_order="false",
    order_lines=None,
    require_attention=False,
):
    """
    Call i-plan to request reserve orders
    :params orders: list e-ordering order
    :return: i-plan response
    """
    list_alternate_materials = {}
    request_headers = []
    if update_items or require_attention:
        request_header = prepare_request_header_ctp_ctp(
            order,
            update_items,
            list_alternate_materials,
            is_dummy_order,
            require_attention=True,
            accept_confirm_date=False,
        )
        request_headers.append(request_header)
    elif order_lines:
        request_header = prepare_request_header_ctp_ctp(
            order, order_lines, list_alternate_materials, is_dummy_order
        )
        request_headers.append(request_header)

    request_id = str(uuid.uuid1().int)
    request_params = {
        "DDQRequest": {
            "requestId": request_id,
            "sender": "e-ordering",
            "DDQRequestHeader": request_headers,
        }
    }

    # Hard code response
    # TODO: remove after i-plan is ready
    # Start hard code response
    response_headers = []
    response_lines = []
    for line in update_items:
        response_lines.append(
            {
                "lineNumber": str(line.item_no),
                "productCode": "productCodeA01",
                "status": "Confirmed",
                "deliveryDate": "2022-09-12T09:11:49.661Z",
                "dispatchDate": "2022-09-12T09:11:49.661Z",
                "quantity": 444,
                "unit": "BU_SaleUnitA01",
                "onHandStock": True,
                "warehouseCode": "WareHouseCodeA01",
                "returnStatus": "Partial Success",
                "returnCode": "Only X Tonnes available",
                "returnCodeDescription": "returnCodeDescriptionA01",
                "DDQResponseOperation": [],
            }
        )
    response_headers.append(
        {
            "headerCode": "AA112233",
            "DDQResponseLine": response_lines,
        }
    )

    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.IPLAN.value
    ).request_mulesoft_post(
        IPlanEndPoint.I_PLAN_REQUEST.value, request_params, encode=True
    )
    return response


def prepare_request_header_ctp_ctp(
    order,
    order_lines,
    list_alternate_materials,
    is_dummy_order="true",
    require_attention=False,
    accept_confirm_date=False,
):
    request_lines = []
    consignmentLocation = get_contract_consignment_location_from_order(order)
    for order_line in order_lines:
        request_date = (
            order_line.request_date
            and order_line.request_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            or ""
        )
        if accept_confirm_date:
            request_date = (
                order_line.confirmed_date
                and order_line.confirmed_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                or ""
            )
        alternate_products = None
        if order_line.material_variant:
            alternate_products = list_alternate_materials.get(
                order_line.material_variant.id
            )

        parameter = change_parameter_follow_inquiry_method(order_line, order)
        inquiry_method = parameter.get("inquiry_method")
        use_inventory = parameter.get("use_inventory")
        use_consignment_inventory = parameter.get("use_consignment_inventory")
        use_projected_inventory = parameter.get("use_projected_inventory")
        use_production = parameter.get("use_production")
        order_split_logic = parameter.get("order_split_logic").upper()
        single_source = parameter.get("single_source")
        re_atp_required = parameter.get("re_atp_required")

        # I-plan unique customer code
        fmt_sold_to_code = (
            order.sold_to and order.sold_to.sold_to_code or order.sold_to_code or ""
        ).lstrip("0") or None
        request_line = {
            "inquiryMethod": inquiry_method,
            "useInventory": use_inventory,
            "useConsignmentInventory": use_consignment_inventory,
            "useProjectedInventory": use_projected_inventory,
            "useProduction": use_production,
            "orderSplitLogic": order_split_logic,
            "singleSourcing": single_source,
            "lineNumber": str(order_line.item_no),
            "locationCode": fmt_sold_to_code,
            "productCode": order_line.material_variant.code
            if order_line.material_variant
            else (order_line.material_code or ""),
            "quantity": str(order_line.quantity) if order_line.quantity else "0",
            "typeOfDelivery": IPlanTypeOfDelivery.EX_MILL.value,
            "requestType": "NEW" if not require_attention else "AMENDMENT",
            "unit": "ROL",
            "transportMethod": "Truck",
            "reATPRequired": re_atp_required,
            "requestDate": request_date,
            "consignmentOrder": False,
            "consignmentLocation": consignmentLocation,
            "fixSourceAssignment": order_line.plant or "",
            "DDQSourcingCategories": [
                {"categoryCode": order.sales_organization.code},
                {"categoryCode": order.sales_group.code},
            ],
        }
        if alternate_products and len(alternate_products):
            request_line["DDQAlternateProducts"] = alternate_products
        request_lines.append(request_line)
    params = {
        "headerCode": str(uuid.uuid1().int)[:LEN_OF_HEADER_CODE]
        if not require_attention
        else order.so_no.lstrip("0"),
        "autoCreate": False,  # TRUE for dummy order FALSE for customer order
        "DDQRequestLine": request_lines,
    }
    # TODO: remove this condition if required for all types
    return params


def filter_no_outsource_order_lines(order_lines=None, order=None):
    """Filter out outsource order lines
    Args:
        order_lines (list, optional): order lines. Defaults to [].
    Returns:
        list: no outsource order lines
    """
    order_lines = order_lines or []
    os_plant_list = MaterialType.MATERIAL_OS_PLANT.value

    def _filter(line):
        item_cat_eo = line.item_cat_eo or ""
        material_plant = line.contract_material and line.contract_material.plant or ""
        plant = line.plant or ""
        if not plant and (material_plant in os_plant_list):
            return False

        if item_cat_eo == ItemCat.ZKC0.value or (plant in os_plant_list):
            return False
        return True

    filter_lines = []
    material_os_lines = []
    for line in order_lines:
        if _filter(line):
            filter_lines.append(line)
        else:
            material_os_lines.append(line)

    if order and len(material_os_lines) > 0:
        # in EOUpload, etd is string (original)
        _confirmed_date = order.etd if order.etd else None
        confirmed_date = date_to_sap_date(_confirmed_date, "%Y-%m-%d")
        for line in material_os_lines:
            line.confirmed_date = confirmed_date
        sap_migration_models.OrderLines.objects.bulk_update(
            material_os_lines, ["confirmed_date"]
        )
    return filter_lines


def confirm_i_plan(
    i_plan_response,
    status,
    manager,
    sap_order_number=None,
    sap_response=None,
    order=None,
    order_lines=None,
    require_attention=False,
):
    """
    Commit or Rollback iPlan response
    @param i_plan_response:
    @param status:
    @param manager:
    @param sap_order_number:
    @param sap_response:
    @param order: eOrdering order object
    @param order_lines: param for walking around issue SEO-2741
    @return:
    """
    confirm_headers = []
    response_headers = i_plan_response.get("DDQResponse").get("DDQResponseHeader")
    dict_order_schedules_out = {}

    if sap_response:
        order_schedules_outs = sap_response.get("orderSchedulesOut", [])
        dict_order_schedules_out = {
            str(order_schedule["itemNo"]).lstrip("0"): order_schedule["confirmQty"]
            for order_schedule in order_schedules_outs
        }

    order_lines = order_lines or sap_migration_models.OrderLines.objects.filter(
        order=order, iplan__isnull=False
    )
    dict_order_lines = {}
    for o_line in order_lines:
        dict_order_lines[str(o_line.original_item_no or o_line.item_no)] = o_line

    for response_header in response_headers:
        i_plan_order_lines = response_header.get("DDQResponseLine")
        confirm_lines = []
        for line in i_plan_order_lines:
            line_number = str(line.get("lineNumber")).lstrip("0")
            item_no = str(int(float(line_number)))
            if (
                line.get("returnStatus").lower()
                != IPLanResponseStatus.FAILURE.value.lower()
            ):
                on_hand_quantity_confirmed = 0
                order_line = dict_order_lines.get(item_no)

                # item_cat_eo = None
                # if order_line:
                #     item_cat_eo = order_line.item_cat_eo
                if dict_order_schedules_out:
                    on_hand_quantity_confirmed = dict_order_schedules_out.get(
                        str(line_number), 0
                    )

                # Remove this code as new spec in SEO-2499
                # if item_cat_eo and item_cat_eo == "ZKSO":
                #     on_hand_quantity_confirmed = str(line.get("quantity")) or 0

                if (
                    order.type == OrderType.EXPORT.value
                    and order_line.iplan.atp_ctp_detail
                    in (AtpCtpStatus.ATP_FUTURE.value, AtpCtpStatus.CTP.value)
                ):
                    on_hand_quantity_confirmed = 0

                # if Order is "CTP" then onHandQuantityConfirmed = 0
                if line.get("onHandStock", True) is False:
                    on_hand_quantity_confirmed = 0

                order_information_type = []
                if (
                    order.type == OrderType.EXPORT.value
                    and status == IPLanConfirmStatus.COMMIT.value
                ):
                    contract_no = get_contract_no_from_order(order)
                    country = get_ship_to_country_from_order(order)
                    sold_to_name = get_sold_to_name_es14_partneraddress_from_order(
                        order
                    )
                    shipping_remark = get_shipping_remark_from_order(order)
                    order_information_item = []
                    if order.eo_upload_log:
                        shipping_remark = order.shipping_mark

                    if shipping_remark:
                        order_information_item.append(
                            {
                                "valueType": "ShippingMarks",
                                "value": shipping_remark,
                            }
                        )
                    if contract_no:
                        order_information_item.append(
                            {
                                "valueType": "ProformaInvoice",
                                "value": str(int(contract_no))
                                if contract_no.isdigit()
                                else contract_no,
                            }
                        )
                    if sold_to_name:
                        order_information_item.append(
                            {"valueType": "SoldTo", "value": sold_to_name}
                        )

                    if not order.eo_upload_log:
                        if country:
                            order_information_item.append(
                                {"valueType": "Country", "value": country}
                            )

                    order_information_type.append(
                        {
                            "type": "CustomInfo",
                            "DDQOrderInformationItem": order_information_item,
                        }
                    )
                confirm_line = {
                    "lineNumber": order_line.item_no
                    if order_line
                    else str(int(float(line_number))),
                    "originalLineNumber": line_number,
                    "onHandQuantityConfirmed": str(on_hand_quantity_confirmed),
                    "unit": line.get("unit"),
                    "status": status,
                    "DDQOrderInformationType": []
                    if require_attention
                    else order_information_type,
                }
            else:
                confirm_line = {
                    "lineNumber": str(int(float(line_number))),
                    "originalLineNumber": line_number,
                    "status": status,
                    "DDQOrderInformationType": [],
                }

            confirm_lines.append(confirm_line)

        if status == IPLanConfirmStatus.COMMIT.value and sap_order_number:
            header_code = sap_order_number.lstrip("0")
        else:
            header_code = response_header.get("headerCode").lstrip("0")
        confirm_headers.append(
            {
                "headerCode": header_code,
                "originalHeaderCode": response_header.get("headerCode").lstrip("0")
                if not require_attention
                else header_code,
                "DDQConfirmLine": confirm_lines,
            }
        )

    confirm_params = {
        "DDQConfirm": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQConfirmHeader": confirm_headers,
        }
    }

    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.IPLAN.value
    ).request_mulesoft_post(
        IPlanEndPoint.I_PLAN_CONFIRM.value, confirm_params, encode=True
    )
    return response


def sap_update_order(
    order,
    manager,
    sap_update_flag,
    order_lines_change_request_date=None,
    origin_order_lines=None,
    original_order=None,
    updated_data=None,
    pre_update_lines=None,
    export_delete_flag=True,
    updated_items=None,
    accept_confirm_date=False,
):
    """
    Call SAP ES21 to update order
    @param order:
    @param manager:
    @param sap_update_flag:
    @param order_lines_change_request_date:
    @param origin_order_lines:
    @param original_order:
    @return:
    """
    # Call SAP to update order
    pre_update_lines = pre_update_lines or {}
    updated_items = updated_items or []
    sap_response = request_sap_es21(
        order,
        manager,
        sap_update_flag,
        order_lines_change_request_date,
        origin_order_lines,
        original_order,
        updated_data=updated_data,
        pre_update_lines=pre_update_lines,
        export_delete_flag=export_delete_flag,
        updated_items=updated_items,
        accept_confirm_date=accept_confirm_date,
    )
    sap_response_success = True
    sap_order_messages = []
    sap_item_messages = []
    if sap_response.get("return"):
        for data in sap_response.get("return"):
            if data.get("type") == SAP21.FAILED.value:
                sap_response_success = False
                sap_order_messages.append(
                    {
                        "id": data.get("id"),
                        "number": data.get("number"),
                        "so_no": sap_response.get("salesdocument") or order.so_no,
                        "message": data.get("message"),
                    }
                )
        for item in sap_response.get("orderItemsOut", ""):
            if item.get("itemStatus"):
                sap_item_messages.append(
                    {
                        "item_no": item.get("itemNo"),
                        "item_status": item.get("itemStatus"),
                    }
                )
    # else:
    #     sap_response_success = False
    return sap_response_success, sap_order_messages, sap_item_messages


def request_sap_es21(
    order,
    manager,
    sap_update_flag=None,
    order_lines_change_request_date=None,
    origin_order_lines=None,
    original_order=None,
    updated_data=None,
    pre_update_lines=None,
    export_delete_flag=True,
    updated_items=None,
    accept_confirm_date=False,
):
    pre_update_lines = pre_update_lines or {}
    updated_items = updated_items or []
    sap_update_flag = sap_update_flag or {}
    # path_response_es21 = './scg_checkout/graphql/implementations/response_api_es21.json'
    # response_es21 = response_from_sap(path_response_es21)
    if accept_confirm_date:
        return accept_confirm_date_request_es21(order, manager, updated_items)
    order_type = order.type
    if order_type == OrderType.EXPORT.value:
        return change_order_request_es21(
            order,
            manager,
            sap_update_flag,
            updated_data=original_order,
            pre_update_lines=pre_update_lines,
            export_delete_flag=export_delete_flag,
            updated_items=updated_items,
        )

    order_lines = updated_items or sap_migration_models.OrderLines.objects.filter(
        order=order
    )
    fields_of_order = {
        "po_no": "poNo",
        "po_date": "purchaseDate",
        "customer_group_1_id": "customerGroup1",
        "customer_group_2_id": "customerGroup2",
        "customer_group_3_id": "customerGroup3",
        "customer_group_4_id": "customerGroup4",
        "incoterms_1_id": "incoterms1",
    }
    field_of_order_line = {
        "request_date": "reqDate",
        "quantity": "targetQty",
        "plant": "plant",
        "shipping_point": "shippingPoint",
        "route": "route",
        "po_no": "purchaseNoC",
        # "item_cat_eo": "",
        # "po_no_external": "",
        "delivery_tol_over": "overdlvtol",
        "delivery_tol_unlimited": "unlimitTol",
        "delivery_tol_under": "unddlvTol",
    }
    order_header_in = {
        # "reqDate": order.request_date.strftime("%d/%m/%Y")
        # if order.request_date
        # else "",
        "incoterms1": order.incoterms_1.code if order.incoterms_1 else "",
        # "incoterms2": order.incoterms_2 if order.incoterms_2 else "",
        "poNo": order.po_no if order.po_no else "",
        "purchaseDate": order.po_date.strftime("%d/%m/%Y") if order.po_date else "",
        # "priceGroup": order.price_group if order.price_group else "",
        # "priceDate": order.price_date.strftime("%d/%m/%Y")
        # if order.price_date
        # else "",
        # "currency": order.currency and order.currency.code or order.doc_currency or "",
        # "customerGroup": order.customer_group.code if order.customer_group else "",
        # "salesDistrict": "",
        # "shippingCondition": order.shipping_condition
        # if order.shipping_condition
        # else "",
        "customerGroup1": order.customer_group_1.code if order.customer_group_1 else "",
        "customerGroup2": order.customer_group_2.code if order.customer_group_2 else "",
        "customerGroup3": order.customer_group_3.code if order.customer_group_3 else "",
        "customerGroup4": order.customer_group_4.code if order.customer_group_4 else "",
        "refDoc": order.contract.code if order.contract else "",
    }

    flag_update = {}
    for field, value in fields_of_order.items():
        flag_update[field] = True
        if getattr(order, field, None) == getattr(original_order, field, None):
            flag_update[field] = False
            order_header_in.pop(value, None)

    origin_order_lines_object = {}
    for origin_order_line in origin_order_lines:
        origin_order_lines_object[origin_order_line.item_no] = origin_order_line

    order_partners = []
    order_items_in = []
    order_items_inx = []
    order_schedules_in = []
    order_schedules_inx = []
    order_text = []
    ship_to_partners = {}
    confirm_quantity = 0

    for order_line in order_lines:
        if order_line.ship_to:
            ship_to_partners[order_line.item_no] = order_line.ship_to.split(" - ")[0]

    order_partners = get_order_partner_for_es21(order)

    for line in order_lines:
        if ship_to_partners.get(line.item_no):
            order_partners.append(
                {
                    "partnerRole": "WE",
                    "partnerNumb": ship_to_partners[line.item_no],
                    "itemNo": line.item_no,
                }
            )

    for line in order_lines:
        item_no = line.item_no.zfill(6)
        origin_order_line_object = origin_order_lines_object.get(line.item_no)
        flag_update_line = {}

        request_items_base = {
            "itemNo": item_no,
            "material": line.material_variant.code
            if line.material_variant.code
            else "",
            "targetQty": line.quantity if line.quantity else 0,
            "salesUnit": "EA"
            if line.contract_material.material.material_group == "PK00"
            else "ROL",
            "plant": line.plant or "",
            "shippingPoint": line.shipping_point or "",
            "route": line.route.split(" - ")[0] if line.route else "",
            "purchaseNoC": line.po_no if line.po_no else "",
            # "poItemNo": line.po_item_no if line.po_item_no else "",
            # "itemCategory": line.item_cat_eo or "",
            # "priceGroup1": "",
            # "priceGroup2": "",
            # "poNo": line.po_no if line.po_no else "",
            # "poitemNoS": line.purch_nos if line.purch_nos else "",  # Not sure
            # "usage": "100",
            "overdlvtol": line.delivery_tol_over,
            "unlimitTol": "",
            "unddlvTol": line.delivery_tol_under,
            # "reasonReject": "",
            # "paymentTerms": line.payment_term_item
            # if line.payment_term_item
            # else "",
            # "denominato": 1,
            # "numconvert": 1000,
            "refDoc": line.ref_doc if line.ref_doc else "",
            "refDocIt": line.contract_material and line.contract_material.item_no or "",
            # "flgUpdateContract": "",
        }
        # if sap_update_flag.get(str(line.item_no), "U") == SapUpdateFlag.INSERT.value:
        #     request_items_base["refDoc"] = line.ref_doc if line.ref_doc else ""
        #     request_items_base["refDocIt"] = line.contract_material and line.contract_material.item_no or ""

        if line.delivery_tol_unlimited:
            request_items_base["overdlvtol"] = 0
            request_items_base["unlimitTol"] = "X"
            request_items_base["unddlvTol"] = 0
            # request_items_base.pop("overdlvtol")
            # request_items_base.pop("unddlvTol")

        if not line.delivery_tol_over:
            request_items_base.pop("overdlvtol")

        if not line.delivery_tol_under:
            request_items_base.pop("unddlvTol")

        for field, value in field_of_order_line.items():
            flag_update_line[field] = True
            if getattr(origin_order_line_object, field, None) == getattr(
                line, field, None
            ):
                flag_update_line[field] = False
                request_items_base.pop(value, None)

        order_items_in.append(request_items_base)

        order_items_inx.append(
            {
                "itemNo": item_no,
                "updateflag": sap_update_flag.get(str(line.item_no), "U"),
                "targetQty": flag_update_line["quantity"],
                "salesUnit": False,
                "plant": flag_update_line["plant"],
                "shippingPoint": flag_update_line["shipping_point"],
                "route": flag_update_line["route"],
                "custPoNo": flag_update_line["po_no"],
                # "poItemNo": True,
                # "itemCategory": False,
                # "priceGroup1": False,
                # "priceGroup2": False,
                # "poNo": True,
                # "poitemNoS": True,
                # "usage": True,
                "overdlvtol": flag_update_line["delivery_tol_over"],
                "unlimitTol": flag_update_line["delivery_tol_unlimited"],
                "unddlvTol": flag_update_line["delivery_tol_under"],
                # "reasonReject": True,
                # "paymentTerms": True,
                # "denominato": True,
                # "numconvert": True,
            }
        )
        if line.iplan:
            confirm_quantity = (
                line.iplan.iplant_confirm_quantity if line.i_plan_on_hand_stock else 0
            )
        # if line.item_cat_eo == ItemCat.ZKSO.value:
        #     confirm_quantity = line.target_quantity or 0
        if line.item_cat_eo == ItemCat.ZKC0.value:
            confirm_quantity = line.quantity or 0

            # Todo: improve late
        order_schedule_in = {
            "itemNo": item_no,
            "scheduleLine": "0001",
            "reqDate": line.request_date.strftime("%d/%m/%Y")
            if line.request_date
            else "",
            "reqQty": line.quantity,
            "confirmQty": confirm_quantity or 0,
            "deliveryBlock": "09"
            if line and line.iplan and line.request_date != line.iplan.original_date
            else "",
        }

        for field in ["request_date", "quantity"]:
            flag_update_line[field] = True
            if getattr(origin_order_line_object, field, None) == getattr(
                line, field, None
            ):
                flag_update_line[field] = False
                if field == "request_date":
                    order_schedule_in.pop("reqDate", None)
                if field == "quantity":
                    order_schedule_in.pop("reqQty", None)
        order_schedules_in.append(order_schedule_in)
        order_schedules_inx.append(
            {
                "itemNo": item_no,
                "scheduleLine": "0001",
                "updateflag": sap_update_flag.get(str(line.item_no), "U"),
                # "scheduleLinecate": False,
                "requestDate": flag_update_line["request_date"],
                "requestQuantity": flag_update_line["quantity"],
                "confirmQuantity": True,
                "deliveryBlock": True,
            }
        )

        # if order_type != OrderType.EXPORT.value:
        # order_conditions_in.append(
        #     {
        #         "itemNo": item_no,
        #         "conditionType": "ZPR2",
        #         "conditionValue": 4816,
        #         "currency": order.currency and order.currency.code or order.doc_currency or "",
        #         "conditionUnit": "ROL",
        #         "conditionPUnit": "1",
        #     }
        # )
        # order_conditions_inx.append(
        #     {
        #         "itemNo": item_no,
        #         "conditionType": "ZPR2",
        #         "updateFlag": sap_update_flag.get(str(line.item_no), "U"),
        #         "conditionValue": True,
        #         "currency": True,
        #         "conditionUnit": True,
        #         "conditionPUnit": True,
        #     }
        # )

    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order.so_no,
        "testrun": False,
        "orderHeaderIn": order_header_in,
        "orderHeaderInX": {
            # "reqDate": True,
            "incoterms1": flag_update["incoterms_1_id"],
            # "incoterms2": False,
            "poNo": flag_update["po_no"],
            "purchaseDate": flag_update["po_date"],
            # "priceGroup": True,
            # "priceDate": True,
            # "currency": True,
            # "customerGroup": True,
            # "salesDistrict": True,
            # "shippingCondition": True,
            "customerGroup1": flag_update["customer_group_1_id"],
            "customerGroup2": flag_update["customer_group_2_id"],
            "customerGroup3": flag_update["customer_group_3_id"],
            "customerGroup4": flag_update["customer_group_4_id"],
        },
        "orderPartners": order_partners,
        "orderItemsIn": order_items_in,
        "orderItemsInx": order_items_inx,
        "orderSchedulesIn": order_schedules_in,
        "orderSchedulesInx": order_schedules_inx,
        # "orderConditionsIn": order_conditions_in,
        # "orderConditionsInX": order_conditions_inx,
    }
    order_text = prepare_param_es21_order_text_for_change_order_domestic(
        order, order_lines, order_lines_change_request_date, dtr_dtp_update=False
    )
    if order_text:
        params["orderText"] = order_text

    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.SAP.value
    ).request_mulesoft_post(SapEnpoint.ES_21.value, params, encode=True)
    return response


def change_order_request_es21(
    order,
    manager,
    sap_update_flag=None,
    updated_data=None,
    pre_update_lines=None,
    export_delete_flag=True,
    updated_items=None,
):
    pre_update_lines = pre_update_lines or {}
    updated_items = updated_items or []
    order_lines = updated_items or sap_migration_models.OrderLines.objects.filter(
        order=order
    )

    order_partners = []
    order_items_in = []
    order_items_inx = []
    order_schedules_in = []
    order_schedules_inx = []
    order_text = []
    item_no_order_header = "000000"
    sold_to_code = order.sold_to.sold_to_code if order.sold_to else order.sold_to_code

    if order.payer:
        payer = order.payer.split("-")[0].strip()
        partner = master_models.SoldToChannelPartnerMaster.objects.filter(
            sold_to_code=sold_to_code, partner_code=payer
        ).last()
        if partner:
            order_partners.append(
                {
                    "partnerRole": "RG",
                    "partnerNumb": payer,
                    "itemNo": item_no_order_header,
                    # "addressLink": partner.address_link
                }
            )

    if order.ship_to:
        ship_to = order.ship_to.split("-")[0].strip()
        partner = master_models.SoldToChannelPartnerMaster.objects.filter(
            sold_to_code=sold_to_code, partner_code=ship_to
        ).last()
        if partner:
            order_partners.append(
                {
                    "partnerRole": "WE",
                    "partnerNumb": ship_to,
                    "itemNo": item_no_order_header,
                    # "addressLink": partner.address_link
                }
            )

    if order.bill_to:
        bill_to = order.bill_to.split("-")[0].strip()
        partner = master_models.SoldToChannelPartnerMaster.objects.filter(
            sold_to_code=sold_to_code, partner_code=bill_to
        ).last()
        if partner:
            order_partners.append(
                {
                    "partnerRole": "RE",
                    "partnerNumb": bill_to,
                    "itemNo": item_no_order_header,
                    # "addressLink": partner.address_link
                }
            )
    for line in order_lines:
        remark = line.remark or ""

        # reject_reason = "93" if line.reject_reason == "Yes" else ""
        old_order_line = pre_update_lines.get(line.id)
        item_no = line.item_no.zfill(6)
        (
            order_item,
            order_item_in,
            order_schedule_in,
            order_schedule_inx,
        ) = create_es21_order_items(
            line,
            old_order_line,
            sap_update_flag.get(str(line.item_no), "U"),
            delete_flag=export_delete_flag,
        )

        order_items_in.append(order_item)
        order_items_inx.append(order_item_in)
        if order_schedule_in:
            order_schedules_in.append(order_schedule_in)
        if order_schedule_inx:
            order_schedules_inx.append(order_schedule_inx)

        handle_request_text_to_es21(
            order_text, remark, item_no, TextID.ITEM_REMARK.value
        )

    etd = (
        datetime.strptime(order.etd, "%Y-%m-%d").strftime("%d%m%Y") if order.etd else ""
    )
    eta = (
        datetime.strptime(str(order.eta), "%Y-%m-%d").strftime("%d%m%Y")
        if order.eta
        else ""
    )
    payment_instruction = order.payment_instruction or ""
    port_of_discharge = order.port_of_discharge or ""
    port_of_loading = order.port_of_discharge or ""
    no_of_containers = order.no_of_containers or ""
    dlc_expiry_date = (
        order.dlc_expiry_date.strftime("%d%m%Y") if order.dlc_expiry_date else ""
    )
    dlc_latest_delivery_date = (
        order.dlc_latest_delivery_date.strftime("%d%m%Y")
        if order.dlc_latest_delivery_date
        else ""
    )
    dlc_no = order.dlc_no or ""
    uom = order.uom or ""
    gw_uom = order.gw_uom or ""
    product_information = order.production_information or ""
    remark = order.remark or ""
    internal_comments_to_warehouse = order.internal_comment_to_warehouse or ""

    handle_request_text_to_es21(
        order_text, product_information, item_no_order_header, TextID.HEADER_PI.value
    )
    handle_request_text_to_es21(
        order_text,
        internal_comments_to_warehouse,
        item_no_order_header,
        TextID.HEADER_ICTW.value,
    )
    handle_request_text_to_es21(
        order_text, remark, item_no_order_header, TextID.HEADER_REMARK.value
    )
    handle_request_text_to_es21(
        order_text, payment_instruction, item_no_order_header, TextID.HEADER_PAYIN.value
    )
    handle_request_text_to_es21(
        order_text, etd, item_no_order_header, TextID.HEADER_ETD.value
    )
    handle_request_text_to_es21(
        order_text, eta, item_no_order_header, TextID.HEADER_ETA.value
    )
    handle_request_text_to_es21(
        order_text,
        port_of_discharge,
        item_no_order_header,
        TextID.HEADER_PORT_OF_DISCHARGE.value,
    )
    handle_request_text_to_es21(
        order_text,
        port_of_loading,
        item_no_order_header,
        TextID.HEADER_PORT_OF_LOADING.value,
    )
    handle_request_text_to_es21(
        order_text,
        no_of_containers,
        item_no_order_header,
        TextID.HEADER_NO_OF_CONTAINERS.value,
    )
    handle_request_text_to_es21(
        order_text,
        dlc_expiry_date,
        item_no_order_header,
        TextID.HEADER_DLC_EXPIRY_DATE.value,
    )
    handle_request_text_to_es21(
        order_text,
        dlc_latest_delivery_date,
        item_no_order_header,
        TextID.HEADER_DLC_LATEST_DELIVERY_DATE.value,
    )
    handle_request_text_to_es21(
        order_text, dlc_no, item_no_order_header, TextID.HEADER_DLC_NO.value
    )
    handle_request_text_to_es21(
        order_text, uom, item_no_order_header, TextID.HEADER_UOM.value
    )
    handle_request_text_to_es21(
        order_text, gw_uom, item_no_order_header, TextID.HEADER_GW_UOM.value
    )

    order_header_in, order_header_in_x = get_order_header_es21(
        order=updated_data, updated_order=order
    )
    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order.so_no,
        "testrun": False,
        "orderHeaderIn": {
            **order_header_in,
            "refDoc": order.contract.code if order.contract else "",
        },
        "orderHeaderInX": {
            **order_header_in_x,
        },
        "orderPartners": order_partners,
        "orderItemsIn": order_items_in,
        "orderItemsInx": order_items_inx,
        "orderSchedulesIn": order_schedules_in,
        "orderSchedulesInx": order_schedules_inx,
    }
    if order_text:
        params["orderText"] = order_text

    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.SAP.value
    ).request_mulesoft_post(SapEnpoint.ES_21.value, params, encode=True)
    return response


def create_es21_order_items(
    new_order_line: sap_migration_models.OrderLines,
    old_order_line: sap_migration_models.OrderLines,
    flag="U",
    delete_flag=True,
):
    # check if field in order item is updated or item is created
    def _field_updated(field: str):
        return _is_updated(field, new_order_line, old_order_line) or flag == "I"

    material_code = (
        new_order_line.material_variant.code if new_order_line.material_variant else ""
    )
    item_no = new_order_line.item_no.zfill(6)
    order_item = {"itemNo": item_no, "material": material_code}

    if flag == "D" and delete_flag:
        order_item.update(
            {"refDoc": new_order_line.ref_doc if new_order_line.ref_doc else ""}
        )
        order_item.update(
            {
                "refDocIt": new_order_line.contract_material
                and new_order_line.contract_material.item_no
                or ""
            }
        )
        order_item_inx = {"itemNo": item_no, "updateflag": "D"}
        return order_item, order_item_inx, {}, {}

    target_quantity = new_order_line.quantity or 0
    shipping_point = (
        new_order_line.shipping_point.split("-")[0].strip()
        if new_order_line.shipping_point
        else ""
    )
    route = new_order_line.route.split(" - ")[0] if new_order_line.route else ""
    po_no = new_order_line.po_no or ""
    reject_reason = "93" if new_order_line.reject_reason == "Yes" else ""
    _update_base(
        _field_updated("material_variant.code"), order_item, "material", material_code
    )
    _update_base(_field_updated("quantity"), order_item, "targetQty", target_quantity)
    _update_base(
        _field_updated("plant"), order_item, "plant", new_order_line.plant or ""
    )
    _update_base(
        _field_updated("shipping_point"), order_item, "shippingPoint", shipping_point
    )
    _update_base(_field_updated("route"), order_item, "route", route)
    _update_base(_field_updated("po_no"), order_item, "poNo", po_no)
    _update_base(
        _field_updated("delivery_tol_over"),
        order_item,
        "overdlvtol",
        new_order_line.delivery_tol_over,
    )
    _update_base(
        _field_updated("delivery_tol_unlimited"),
        order_item,
        "unlimitTol",
        "X" if new_order_line.delivery_tol_unlimited else "",
    )
    _update_base(
        _field_updated("delivery_tol_under"),
        order_item,
        "unddlvTol",
        new_order_line.delivery_tol_under,
    )
    _update_base(
        _field_updated("reject_reason"), order_item, "reasonReject", reject_reason
    )
    _update_base(
        _field_updated("item_cat_eo"),
        order_item,
        "itemCategory",
        new_order_line.item_cat_eo,
    )

    order_item.update(
        {"refDoc": new_order_line.ref_doc if new_order_line.ref_doc else ""}
    )
    order_item.update(
        {
            "refDocIt": new_order_line.contract_material
            and new_order_line.contract_material.item_no
            or ""
        }
    )
    order_item.update({"saleUnit": new_order_line.sales_unit})

    if order_item.get("delivery_tol_unlimited", None) == "X":
        order_item.update({"delivery_tol_over": 0})
        order_item.update({"delivery_tol_under": 0})

    if not new_order_line.delivery_tol_over and not order_item.get("overdlvtol", None):
        order_item.pop("overdlvtol", None)
    if not new_order_line.delivery_tol_under and not order_item.get("unddlvTol", None):
        order_item.pop("unddlvTol", None)

    order_items_inx = {
        "itemNo": new_order_line.item_no.zfill(6),
        "updateflag": flag,
        "targetQty": True,
        "salesUnit": True,
        "plant": True,
        "shippingPoint": True,
        "route": True,
        "poNo": True,
        "overdlvtol": True,
        "unlimitTol": True,
        "unddlvTol": True,
        "reasonReject": True,
        "saleUnit": True,
        "itemCategory": True,
    }
    keys = deepcopy(list(order_items_inx.keys()))
    for k in keys:
        if k in ["itemNo", "updateflag"]:
            continue
        if order_item.get(k, None) is None:
            order_items_inx.pop(k)

    order_schedule = {"itemNo": item_no, "updateflag": flag}
    item_request_date = (
        new_order_line.request_date.strftime("%d/%m/%Y")
        if new_order_line.request_date
        else ""
    )
    _update_base(
        _field_updated("request_date"), order_schedule, "reqDate", item_request_date
    )
    quantity = new_order_line.quantity
    _update_base(_field_updated("quantity"), order_schedule, "reqQty", quantity)

    new_confirm_quanity = 0
    old_confirm_quantity = 0
    if new_order_line.item_cat_eo == ItemCat.ZKC0.value:
        new_confirm_quanity = new_order_line.quantity or 0
        old_confirm_quantity = old_order_line.quantity or 0

    if new_order_line.iplan:
        new_confirm_quanity = new_order_line.iplan.iplant_confirm_quantity or 0

    if getattrd(old_order_line, "iplan", None):
        old_confirm_quantity = old_order_line.iplan.iplant_confirm_quantity or 0

    _update_base(
        new_confirm_quanity != old_confirm_quantity or flag == "I",
        order_schedule,
        "confirmQty",
        new_confirm_quanity,
    )

    order_schedule_inx_params = {
        "requestDate": "reqDate",
        "requestQuantity": "reqQty",
        "confirmQuantity": "confirmQty",
    }

    order_schedule_inx = {
        "itemNo": item_no,
        "updateflag": flag,
        "requestDate": True,
        "requestQuantity": True,
        "confirmQuantity": True,
    }

    schedule_keys = deepcopy(list(order_schedule_inx.keys()))
    for k in schedule_keys:
        if k in ["itemNo", "updateflag", "scheduleLine"]:
            continue
        if order_schedule.get(order_schedule_inx_params[k], None) is None:
            del order_schedule_inx[k]

    return order_item, order_items_inx, order_schedule, order_schedule_inx


def get_order_header_es21(
    order: sap_migration_models.Order, updated_order: sap_migration_models.Order
):
    order_header_in = {}
    order_header_in_x = {}
    order_header_with_field_mapped_model = {
        "request_date": "reqDate",
        "place_of_delivery": "Incoterms2",
        "po_no": "poNo",
        "description": "description",
        "unloading_point": "unloadingPoint",
        "usage": "usage",
    }
    model_fields = deepcopy(list(order_header_with_field_mapped_model.keys()))
    for k in model_fields:
        if getattr(order, k, None) == getattr(updated_order, k, None):
            del order_header_with_field_mapped_model[k]

    for update_field, param_field in order_header_with_field_mapped_model.items():
        field_data = getattr(updated_order, update_field, None)
        if field_data:
            if isinstance(field_data, date):
                field_data = field_data.strftime("%d/%m/%Y")
            order_header_in.update({param_field: field_data})
            order_header_in_x.update({param_field: True})

    return order_header_in, order_header_in_x


def call_i_plan_update_order(order, update_items, manager, call_type=None):
    """
    call i-plan to update order
    @param order: list e-ordering order
    @param update_items:
    @param manager:
    @param call_type: use for send mail eo upload feature
    @return:
    """
    i_plan_response = request_i_plan_to_update_order(order, update_items, manager)
    i_plan_response_lines = i_plan_response.get("OrderUpdateResponse").get(
        "OrderUpdateResponseLine"
    )

    response_success = True
    # Check commit i-plan success or not to update R5 flag
    update_attention_r5_items = []
    if len(i_plan_response_lines):
        for line in i_plan_response_lines:
            confirm_success_line_ids = []
            if line.get("returnStatus") == IPlanUpdateOrderStatus.SUCCESS.value:
                confirm_success_line_ids.append(line.get("lineCode"))
            else:
                response_success = False

            if len(confirm_success_line_ids):
                for update_item in update_items:
                    if update_item.id in confirm_success_line_ids:
                        update_attention_r5_items.append(update_item)
    if len(update_attention_r5_items):
        update_attention_type_r5(update_attention_r5_items)

    if (not response_success) and call_type == "eo_upload":
        eo_upload_send_email_when_call_api_fail(
            manager, order, "Update", "IPlan", i_plan_response, "iplan_update"
        )
    qs_order_lines = sap_migration_models.OrderLines.objects.filter(order=order)
    dict_order_lines = {}
    for line in qs_order_lines:
        dict_order_lines[line.item_no] = line
    update_confirm_qty_after_call_iplan(dict_order_lines, i_plan_response_lines)


def request_i_plan_to_update_order(order, update_items, manager):
    """
    Call API Order Update i-plan
    @param order:
    @param update_items:
    @param manager:
    @return:
    """
    update_lines = []
    order_number = order.so_no
    for item in update_items:
        # Need update with split spec
        # if {Check order has split item}:
        #     split_lines.append({
        #         "newOrderNumber": item,
        #         "newLineCode": "10",
        #         "deliveryDate": "date",
        #         "quantity": "number",
        #         "unit": "string"
        #     })
        update_line = {
            "orderNumber": order_number.lstrip("0"),
            "lineCode": item.item_no,
            "requestDate": item.request_date
            and item.request_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            or "",
            "quantity": item.quantity,
            "unit": item.sales_unit,
            "deliveryDate": item.confirmed_date
            and item.confirmed_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            or "",
        }
        update_lines.append(update_line)

    request_params = {
        "OrderUpdateRequest": {
            "updateId": str(uuid.uuid1().int),
            "OrderUpdateRequestLine": update_lines,
        }
    }
    log_val = {
        "order_number": order_number,
        "orderid": order.id,
    }

    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.IPLAN.value, **log_val
    ).request_mulesoft_post(
        IPlanEndPoint.I_PLAN_UPDATE_ORDER.value, request_params, encode=True
    )
    return response


def accept_confirm_date_request_es21(order, manager, updated_items):
    order_schedules_in = [
        {
            "itemNo": item.item_no.zfill(6),
            "scheduleLine": "0001",
            "reqDate": item.confirmed_date.strftime("%d/%m/%Y")
            if item.confirmed_date
            else "",
            "reqQty": item.quantity,
            "confirmQty": item.confirm_quantity or item.iplan.iplant_confirm_quantity,
            "deliveryBlock": "",
        }
        for item in updated_items
    ]
    order_schedules_inx = [
        {
            "itemNo": item.item_no.zfill(6),
            "scheduleLine": "0001",
            "updateflag": "U",
            "requestDate": True,
            "requestQuantity": True,
            "confirmQuantity": True,
            "deliveryBlock": True,
        }
        for item in updated_items
    ]
    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order.so_no,
        "testrun": False,
        "orderHeaderIn": {"refDoc": order.so_no},
        "orderHeaderInx": {"reqDate": False},
        "orderSchedulesIn": order_schedules_in,
        "orderSchedulesInx": order_schedules_inx,
    }
    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.SAP.value
    ).request_mulesoft_post(SapEnpoint.ES_21.value, params, encode=True)
    return response


def _rollback_success_items_if_request_fail(
    manager, i_plan_order_lines, header_code, status
):
    ddq_confirm_line = [
        {
            "lineNumber": str(int(float(item.get("lineNumber")))),
            "originalLineNumber": str(int(float(item.get("lineNumber")))),
            "status": status,
            "DDQOrderInformationType": [],
        }
        for item in i_plan_order_lines
        if item.get("returnStatus").lower() == IPLanResponseStatus.SUCCESS.value
    ]
    if not ddq_confirm_line:
        return
    confirm_params = {
        "DDQConfirm": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQConfirmHeader": [
                {
                    "headerCode": header_code,
                    "originalHeaderCode": header_code,
                    "DDQConfirmLine": ddq_confirm_line,
                }
            ],
        }
    }
    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.IPLAN.value
    ).request_mulesoft_post(
        IPlanEndPoint.I_PLAN_CONFIRM.value, confirm_params, encode=True
    )
    return response
