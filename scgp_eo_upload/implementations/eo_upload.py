import json
import logging
import time
from copy import deepcopy

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

import saleor.account.models
from common.helpers import update_instance_fields
from common.newrelic_metric import add_metric_process_order
from saleor.order import OrderStatus
from saleor.plugins.manager import get_plugins_manager
from sap_migration import models
from sap_migration.graphql.enums import InquiryMethodType, OrderType
from sap_migration.models import Contract, Order, OrderLineIPlan, OrderLines
from scg_checkout.graphql.enums import (
    IPlanOrderItemStatus,
    IPlanOrderStatus,
    IPLanResponseStatus,
    ScgOrderStatus,
)
from scg_checkout.graphql.helper import (
    convert_date_time_to_timezone_asia,
    get_date_time_now_timezone_asia,
    is_materials_product_group_matching,
    make_order_header_text_mapping,
)
from scg_checkout.graphql.implementations.iplan import (
    call_i_plan_create_order,
    call_i_plan_update_order_eo_upload,
    get_address_from_order,
    get_contract_no_name_from_order,
    get_material_description_from_order_line,
    get_order_remark_order_info,
    get_payment_method_name_from_order,
    get_qty_ton_from_order_line,
    get_sale_org_name_from_order,
    get_sales_unit_from_order_line,
    get_sold_to_no_name,
    get_stands_for_company,
    request_api_change_order,
)
from scg_checkout.graphql.resolves.contracts import (
    call_sap_api_get_contracts_export_pis,
    get_data_from_order_text_list,
    sync_contract_material,
    sync_contract_sale_detail,
    sync_lang_from_order_text_list_or_db,
)
from scgp_eo_upload.constants import (
    EO_UPLOAD_STATE_ERROR,
    EO_UPLOAD_STATE_RECEIVED_ORDER,
)
from scgp_eo_upload.models import EoUploadLog, EoUploadLogOrderType
from scgp_export.graphql.helper import is_container
from scgp_export.implementations.mapping_data_object import MappingDataToObject
from scgp_export.implementations.sap import get_web_user_name
from scgp_po_upload.graphql.helpers import html_to_pdf


def _get_error_message(response):
    # improve this
    if response.get("success"):
        return None
    return "Failed to create order"


@transaction.atomic
def sync_eo_upload():
    manager = get_plugins_manager()
    plugin = manager.get_plugin("scg.sqs_eo_upload")
    messages = plugin.sqs_receive_message()
    logging.info(f"[EO Upload] get data from sqs { messages }")
    for message in messages:
        body = json.loads(message.body)
        message_type = body.get("Type")
        if message_type != "Notification":
            continue
        eo_upload_log_id = None
        try:
            eo_upload_log_id = body.get("Message")
            if not eo_upload_log_id:
                raise ValueError("Failed to receive from SQS")
            if eo_upload_log_id:
                logging.info(f"[EO Upload] Consuming message logID {eo_upload_log_id}")
                create_change_export_order(eo_upload_log_id)
        except Exception as e:
            if eo_upload_log_id:
                logging.exception(
                    "[EO Upload] Running failed logID "
                    + eo_upload_log_id
                    + " with exception "
                    + str(e)
                )
            else:
                logging.exception("[EO Upload] Running failed with exception " + str(e))
        try:
            # XXX: if error: continue
            message.delete()
        except Exception:
            pass
    return 1


@transaction.atomic
def log_state(order_id, state, error_message=None):
    log_obj = EoUploadLog.objects.filter(orderid=order_id).last()
    if not log_obj:
        return
    log_obj.state = state
    if error_message:
        log_obj.error_message = error_message
    log_obj.save()


def eo_log_state(log_key, state, error_message=None, order_type=None, order_id=None):
    try:
        with transaction.atomic():
            log_obj = EoUploadLog.objects.filter(log_key=log_key).last()
            if not log_obj:
                return
            log_obj.state = state
            log_obj.order_type = order_type
            log_obj.orderid = order_id
            log_obj.updated_at = timezone.now()
            if error_message:
                log_obj.error_message = error_message
            log_obj.save()
    except Exception:
        pass


def eo_log_so_no(log_key, so_no):
    try:
        with transaction.atomic():
            log_obj = EoUploadLog.objects.filter(log_key=log_key).last()
            if not log_obj:
                return
            log_obj.eo_no = so_no
            log_obj.save()
    except Exception:
        pass


def call_iplan_and_sap_eo_data(order_type, order_object):
    # TODO: log data
    # TODO: improve this
    order_object.status_sap = "confirmed ctp/atp"
    order_type = order_type.lower()
    if order_type == "new":  # or is empty
        if call_sap_api_save(order_object):
            order_object.status_sap = "confirm save sap"
        else:
            order_object.status_sap = "reject save sap"
    elif order_type == "change" or order_type == "split":  # update case
        if call_sap_api_update(order_object):
            order_object.status_sap = "confirm update sap"
        else:
            order_object.status_sap = "reject update sap"

    return order_object


def call_sap_api_save(order):
    log_obj = EoUploadLog.objects.filter(orderid=order.id).last()
    payload = log_obj.payload or {}
    manager = get_plugins_manager()
    response = call_i_plan_create_order(order, manager, call_type="eo_upload")

    err_msg = _get_error_message()
    if err_msg:
        log_state(order.id, EO_UPLOAD_STATE_ERROR, err_msg)
        return None
        # raise Exception(err_msg)
    order_line = list(OrderLines.objects.filter(order_id=order.id))
    order_line.sort(key=lambda line: int(line.item_no))

    data = [
        {
            "item_no": line.item_no,
            "material_description": get_material_description_from_order_line(line),
            "qty": line.quantity,
            "sales_unit": get_sales_unit_from_order_line(line),
            "qty_ton": get_qty_ton_from_order_line(line),
            "request_delivery_date": line.request_date,
            "iplan_confirm_date": line.confirmed_date if line.confirmed_date else "",
        }
        for line in order_line
    ]
    ship_to = order.ship_to and order.ship_to.split("\n")
    created_by = order.created_by
    template_pdf_data = {
        "order_number": order.order_no,
        "customer_po_number": order.po_no,
        "file_name": order.order_no if order.order_no else "",
        "place_of_delivery": order.ship_to or "",
        "payment_terms": order.payment_term,
        "shipping": "ส่งให้",
        "contract_number": get_data_path(payload, "initial.contract"),
        "note": order.item_note,
        "po_no": order.po_no,
        "sale_org_name": get_sale_org_name_from_order(order),
        "so_no": order.so_no,
        "date_time": convert_date_time_to_timezone_asia(order.created_at),
        "sold_to_no_name": get_sold_to_no_name(order.contract.sold_to.sold_to_code),
        "sold_to_address": get_address_from_order(order, "AG"),
        "ship_to_no_name": ship_to and ship_to[0] or "",
        "ship_to_address": ship_to[1] if ship_to and len(ship_to) == 2 else "",
        "payment_method_name": get_payment_method_name_from_order(order),
        "contract_no_name": get_contract_no_name_from_order(order),
        "remark_order_info": get_order_remark_order_info(order),
        "created_by": f"{created_by.first_name} {created_by.last_name}",
        "data": data,
        "file_name_pdf": "Example",
        "print_date_time": get_date_time_now_timezone_asia(),
    }
    template_data = {
        "order_number": order.so_no or order.eo_no,
        "customer_po_number": order.po_no,
        "file_name": order.order_no if order.order_no else "",
        "payment_terms": order.payment_term,
        "shipping": "ส่งให้",
        "contract_number": get_data_path(payload, "initial.contract"),
        "note": order.item_note,
    }
    pdf = html_to_pdf(
        template_pdf_data, "eo_upload_header.html", "eo_upload_content.html"
    )

    if not response.get("success"):
        template_data["status"] = "rejected save SAP"
    if response.get("success") == True:
        template_data["status"] = "confirmed save SAP"
    # Set order status
    order.status = response.get("order_status")
    order.status_thai = IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order.status)
    order.save()
    subject = "TCP Order submitted : %s" % order.eo_no
    if order.contract and order.contract.project_name:
        subject += " - %s" % order.contract.project_name
    manager.scgp_po_upload_send_mail(
        "scg.email", "anastueb@scg.com", template_data, subject, "index.html", pdf, None
    )
    return response.get("success")


def call_sap_api_update(order):
    manager = get_plugins_manager()
    order_status, response = call_i_plan_update_order_eo_upload(order, manager)
    # Set order status
    order.status = order_status
    order.status_thai = IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order.status)
    order.save()
    return order_status == ScgOrderStatus.RECEIVED_ORDER.value


def get_data_path(data, path, default=None, parent=False):
    if not path:
        return data
    val = data
    fields = path.split(".")
    if parent:
        fields = fields[:-1]
    for field in fields:
        if not field.isdigit():
            if not isinstance(val, dict):
                return default
            val = val.get(field, default)
        else:
            ind = int(field)
            if not isinstance(val, list) or ind >= len(val):
                return default
            val = val[ind]
    return val


def create_change_export_order(eo_upload_log_id):
    eo_upload_log = (
        EoUploadLog.objects.filter(id=eo_upload_log_id)
        .exclude(state=EO_UPLOAD_STATE_RECEIVED_ORDER)
        .first()
    )
    if not eo_upload_log:
        logging.info("Not found eo upload log id: %s" % eo_upload_log_id)
        return
    payload = eo_upload_log.payload
    log_key = "%s|%s|%s" % (
        get_data_path(payload, "initial.contract"),
        get_data_path(payload, "header.poNo"),
        get_data_path(payload, "initial.lotNo"),
    )
    payload["initial"]["contract"] = (
        payload.get("initial").get("contract").zfill(10)
        if payload.get("initial") and payload.get("initial").get("contract")
        else ""
    )
    create_and_change_type = payload.get("initial").get("createAndChangeType").lower()
    try:
        if not create_and_change_type:
            create_new_export_order(payload, eo_upload_log, log_key)
        if create_and_change_type == "change":
            change_db_export_order(payload, log_key)
        if create_and_change_type == "split":
            split_export_order(payload, log_key)
        logging.info(f"[EO Upload] Running successfully logID {eo_upload_log.id}")
    except Exception as e:
        eo_log_state(
            log_key, EO_UPLOAD_STATE_ERROR, "Fail to create order (%s)" % str(e)
        )
        logging.error(
            "[EO Upload] Error EOUpload.create_change_export_order log id %s: %s"
            % (eo_upload_log.id, e)
        )


@transaction.atomic
def change_db_export_order(payload, log_key):
    from scgp_export.implementations.orders import mock_confirmed_date

    try:
        manager = get_plugins_manager()

        list_update_key = [
            "reject_reason",
            "quantity",
            "quantity_unit",
            "item_cat_pi",
            "item_cat_eo",
            "plant",
            "condition_group1",
            "route",
            "net_price",
            "price_currency",
            "roll_quantity",
            "roll_diameter",
            "roll_core_diameter",
            "remark",
            "pallet_size",
            "roll_per_pallet",
            "pallet_no",
            "package_quantity",
            "packing_list",
            "commission_percent",
            "commission_amount",
            "commission_unit",
            "eo_item_no",
            "ref_pi_no",
            "vat_percent",
            "contract_material_id",
            "weight",
            "weight_unit",
            "type",
            "request_date",
        ]

        header = payload.get("header")
        initial = payload.get("initial")
        items = payload.get("items")
        mapping_data_to_object = MappingDataToObject()
        initial_parts = mapping_data_to_object.map_inital_part(
            initial=initial, header=header
        )
        header_parts = mapping_data_to_object.map_header_part(header)

        order_object_dict = {**initial_parts, **header_parts}
        find_order_object_db = (
            Order.objects.filter(so_no=order_object_dict.get("eo_no"))
            .exclude(info="split")
            .last()
        )
        order_object = Order(**order_object_dict)
        order_object.id = find_order_object_db.id
        order_object.save()
        origin_order_line_objects = {}
        origin_order_lines = list(
            OrderLines.objects.filter(order_id=order_object.id).all()
        )
        for line in origin_order_lines:
            origin_order_line_objects[line.material_code] = line
        update_order_lines = mapping_order_lines_for_create_eo_upload(
            items,
            order_object.contract_id,
            order_object.request_delivery_date,
            order_object.id,
        )
        for line in update_order_lines:
            line.id = origin_order_line_objects[line.material_code].id
        OrderLines.objects.bulk_update(update_order_lines, list_update_key)

        response = request_api_change_order(
            order_object,
            manager,
            origin_order_lines,
            update_order_lines,
            call_type="eo_upload",
        )
        if response.get("success") == True:
            eo_log_state(
                log_key,
                EO_UPLOAD_STATE_RECEIVED_ORDER,
                order_type=EoUploadLogOrderType.UPDATE,
                order_id=order_object.id,
            )
            send_email(
                order_object=order_object,
                manager=manager,
                status="success to change order",
            )
            mock_confirmed_date(order_object)
            mock_request_date(order_object)
        else:
            eo_log_state(
                log_key,
                EO_UPLOAD_STATE_ERROR,
                "Fail to update order",
                order_type=EoUploadLogOrderType.UPDATE,
                order_id=order_object.id,
            )

    except Exception as e:
        eo_log_state(
            log_key,
            EO_UPLOAD_STATE_ERROR,
            "Failed to create order: %s" % str(e),
            order_type=EoUploadLogOrderType.UPDATE,
        )
    return 1


@transaction.atomic
def split_export_order(payload, log_key):
    from scgp_export.implementations.orders import mock_confirmed_date

    try:

        list_update_key = [
            "reject_reason",
            "quantity",
            "quantity_unit",
            "item_cat_pi",
            "item_cat_eo",
            "plant",
            "condition_group1",
            "route",
            "net_price",
            "price_currency",
            "roll_quantity",
            "roll_diameter",
            "roll_core_diameter",
            "remark",
            "pallet_size",
            "roll_per_pallet",
            "pallet_no",
            "package_quantity",
            "packing_list",
            "commission_percent",
            "commission_amount",
            "commission_unit",
            "eo_item_no",
            "ref_pi_no",
            "vat_percent",
            "contract_material_id",
            "weight",
            "weight_unit",
            "type",
            "request_date",
        ]
        manager = get_plugins_manager()

        header = payload.get("header")
        initial = payload.get("initial")
        items = payload.get("items")
        mapping_data_to_object = MappingDataToObject()
        initial_parts = mapping_data_to_object.map_inital_part(
            initial=initial, header=header
        )
        header_parts = mapping_data_to_object.map_header_part(header)

        order_object_dict = {**initial_parts, **header_parts}
        find_order_object_db = Order.objects.filter(
            eo_no=order_object_dict.get("eo_no")
        ).last()
        order_object = Order(**order_object_dict)
        order_object.info = "split"
        origin_order_lines = OrderLines.objects.filter(
            order_id=find_order_object_db.id
        ).all()
        items_update, items_origin = [], []
        order_line_objects = {
            order_line.material_code: order_line for order_line in origin_order_lines
        }

        for item in items:
            item_db = order_line_objects.get(item["materialCode"])
            if item_db:
                if item_db.quantity - item.get("orderQuantity", 0) < 0:
                    raise ValueError("No remaining quantity")
                new_quantity = item_db.quantity - item.get("orderQuantity", 0)
                items_origin.append(item_db)
                update_item = deepcopy(item_db)
                update_item.__dict__.update({"quantity": new_quantity})
                delattr(update_item, "_django_version")
                items_update.append(update_item)
        OrderLines.objects.bulk_update(items_update, list_update_key)
        split_change_response = request_api_change_order(
            find_order_object_db,
            manager,
            items_origin,
            items_update,
            call_type="eo_upload",
        )

        order_object.save()

        item_parts_create = mapping_order_lines_for_create_eo_upload(
            items,
            order_object.contract_id,
            order_object.request_delivery_date,
            order_object.id,
        )
        OrderLines.objects.bulk_create(item_parts_create)
        split_create_response = call_i_plan_create_order(
            order_object, manager, call_type="eo_upload", user=None
        )
        if split_create_response.get("sap_order_status"):
            order_object.status = split_create_response.get("sap_order_status")
            order_object.save()
        if split_create_response.get("success") and split_change_response.get(
            "success"
        ):
            eo_log_state(
                log_key,
                EO_UPLOAD_STATE_RECEIVED_ORDER,
                order_type=EoUploadLogOrderType.SPLIT,
                order_id=find_order_object_db.id,
            )
            send_email(
                find_order_object_db, manager=manager, status="success to split order"
            )
            mock_confirmed_date(order_object)
        else:
            eo_log_state(
                log_key,
                EO_UPLOAD_STATE_ERROR,
                "Failed to split order",
                order_type=EoUploadLogOrderType.SPLIT,
                order_id=find_order_object_db.id,
            )

    except Exception as e:
        eo_log_state(
            log_key,
            EO_UPLOAD_STATE_ERROR,
            "Failed to create order: %s" % str(e),
            order_type=EoUploadLogOrderType.SPLIT,
        )


def validate_product_group_for_export(order_object_dict, items):
    material_codes = []
    for item in items:
        item["materialCode"] = item.get("materialCode").replace(" ", "")
        material_codes.append(item.get("materialCode"))
    contract_material = models.ContractMaterial.objects.filter(
        contract_id=order_object_dict.get("contract_id"),
        material__materialvariantmaster__code__in=material_codes,
    )

    is_matching_material_group = is_materials_product_group_matching(
        None, contract_material, OrderType.EXPORT.value
    )
    if not is_matching_material_group:
        raise ValueError("Cannot Add Multiple Product Groups to an Order")


@transaction.atomic
def create_new_export_order(payload, eo_upload_log: EoUploadLog = None, log_key=None):
    from scgp_export.implementations.orders import mock_confirmed_date

    start_time = time.time()
    manager = get_plugins_manager()

    header = payload.get("header")
    initial = payload.get("initial")
    items = payload.get("items")
    mapping_data_to_object = MappingDataToObject()
    initial_parts = mapping_data_to_object.map_inital_part(
        initial=initial, header=header
    )
    header_parts = mapping_data_to_object.map_header_part(header)

    order_object_dict = {**initial_parts, **header_parts}
    try:
        validate_product_group_for_export(order_object_dict, items)
    except Exception as e:
        logging.error(
            f"[EO Upload] Failed as the Order Contains Materials with different Product Group : {eo_upload_log.id}"
        )
        eo_log_state(
            log_key, EO_UPLOAD_STATE_ERROR, "Fail to create order (%s)" % str(e)
        )
        raise e
    order_object = Order(**order_object_dict)
    order_object.save()
    order_id = order_object.id
    contract_id = order_object_dict.get("contract_id")
    sync_contract_material(contract_id, context={"order_id": order_id})
    tmp_user = saleor.account.models.User.objects.filter(
        scgp_user__isnull=False
    ).first()
    order_object.web_user_name = get_web_user_name(OrderType.EO, tmp_user)
    # TODO: improve to stamp eo upload log
    if eo_upload_log:
        order_object.eo_upload_log = eo_upload_log
    try:
        for item in items:
            if not is_container(item.get("item_cat_eo")):
                material_code = item.get("materialCode").replace(" ", "")
                contract_material = models.ContractMaterial.objects.filter(
                    contract_id=order_object_dict.get("contract_id"),
                    material__materialvariantmaster__code=material_code,
                ).first()
                order_object.product_group = (
                    contract_material.mat_group_1 if contract_material else None
                )
                break
        order_object.save()
        item_parts_create = mapping_order_lines_for_create_eo_upload(
            items,
            order_object.contract_id,
            order_object.request_delivery_date,
            order_object.id,
        )
        # required
        request_delivery_date = order_object.request_delivery_date
        for item in item_parts_create:
            item.original_request_date = request_delivery_date
        OrderLines.objects.bulk_create(item_parts_create)
        OrderLines.objects.bulk_update(item_parts_create, ["original_request_date"])
        response = call_i_plan_create_order(
            order_object, manager, call_type="eo_upload", user=None
        )
        if response.get("success"):
            sap_order_number = response.get("sap_order_number")
            if sap_order_number:
                eo_log_so_no(log_key, sap_order_number)
            eo_log_state(
                log_key,
                EO_UPLOAD_STATE_RECEIVED_ORDER,
                order_type=EoUploadLogOrderType.CREATE,
                order_id=order_object.id,
            )
            mock_confirmed_date(order_object)
            diff_time = time.time() - start_time
            add_metric_process_order(
                settings.NEW_RELIC_CREATE_ORDER_METRIC_NAME,
                int(diff_time * 1000),
                start_time,
                "SaveOrder",
                order_type=OrderType.EO,
                order_id=order_object.id,
            )
        else:
            # reset when create order failed
            # TODO: improve this
            for item in item_parts_create:
                item.item_status_en = None
                item.item_status_th = None
                item.save()
            order_object.state = OrderStatus.DRAFT
            order_object.save()
            eo_log_state(
                log_key,
                EO_UPLOAD_STATE_ERROR,
                "Failed to create order",
                order_type=EoUploadLogOrderType.CREATE,
                order_id=order_object.id,
            )
        return order_object.id

    except Exception as e:
        raise e


def mapping_order_lines_for_create_eo_upload(
    items, contract_id, request_date, order_id
):
    item_parts = []
    material_codes = []
    for item in items:
        item["materialCode"] = item.get("materialCode").replace(" ", "")
        material_codes.append(item.get("materialCode"))
    contract_material_objects = {}
    contract_material_ids = []
    material_variant_objects = {}
    material_variant_ids = []
    for contract_material in models.ContractMaterial.objects.filter(
        contract_id=contract_id,
        material__materialvariantmaster__code__in=material_codes,
    ):
        contract_material_objects[
            str(contract_material.material.material_code)
        ] = contract_material
        contract_material_ids.append(contract_material.id)

    for material_variant in models.MaterialVariantMaster.objects.filter(
        code__in=material_codes
    ):
        material_variant_objects[str(material_variant.code)] = material_variant
        material_variant_ids.append(material_variant.id)

    for item in items:
        material_code = item.get("materialCode")
        material_variant = material_variant_objects.get(material_code)

        roll_core_diameter = item.get("rollCoreDiameterInch")
        if roll_core_diameter:
            roll_core_diameter = float(str(roll_core_diameter).replace('"', ""))

        roll_diameter = item.get("rollDiameterInch")
        if roll_core_diameter:
            roll_core_diameter = float(str(roll_diameter).replace('"', ""))

        commission_percent = item.get("commissionPercent")
        if commission_percent:
            commission_percent = float(str(commission_percent).replace('"', ""))

        commission_amount = item.get("commission")
        if commission_amount:
            commission_amount = float(str(commission_amount).replace('"', ""))
        # TODO: check this flow
        # if not material_variant:
        #     continue
        # material_code = material_variant and material_variant.material.material_code
        contract_mat_obj = contract_material_objects.get(material_code)
        i_plan = OrderLineIPlan.objects.create(
            attention_type=None,
            atp_ctp=None,
            atp_ctp_detail=None,
            block=None,
            run=None,
            iplant_confirm_quantity=None,
            item_status=None,
            original_date=None,
            inquiry_method_code=None,
            transportation_method=None,
            type_of_delivery=None,
            fix_source_assignment=None,
            split_order_item=None,
            partial_delivery=None,
            consignment=None,
            paper_machine=None,
        )
        item_part = models.OrderLines(
            order_id=order_id,
            reject_reason=item.get("rejectReason"),
            material_code=item.get("materialCode"),
            material_variant=material_variant,
            quantity=item.get("orderQuantity"),
            quantity_unit=item.get("unit"),
            item_cat_pi=item.get("itemCatPi"),
            item_cat_eo=item.get("itemCatEo"),
            plant=item.get("plant"),
            condition_group1=item.get("conditionGroup1"),
            route=item.get("route"),
            net_price=item.get("price", 0),
            price_currency=item.get("priceCurrency"),
            roll_quantity=item.get("noOfRolls"),
            roll_diameter=roll_diameter,
            roll_core_diameter=roll_core_diameter,
            shipping_mark=item.get("remark"),
            remark=None,
            pallet_size=item.get("palletSize"),
            roll_per_pallet=item.get("reamRollPerPallet"),
            pallet_no=item.get("palletNo"),
            package_quantity=item.get("noOfPackage"),
            packing_list=item.get("packingListText"),
            commission_percent=commission_percent,
            commission_amount=commission_amount,
            commission_unit=item.get("commissionCurrency"),
            eo_item_no=item.get("eoItemNo"),
            item_no=item.get("eoItemNo"),
            ref_pi_no=item.get("refPiStock"),
            ref_doc_it=str(item.get("eoItemNo")).zfill(6),
            vat_percent=10,
            contract_material_id=contract_mat_obj and int(contract_mat_obj.id) or None,
            weight=contract_mat_obj and float(contract_mat_obj.weight) or None,
            weight_unit=contract_mat_obj and contract_mat_obj.weight_unit or None,
            type="export",
            inquiry_method=InquiryMethodType.EXPORT.value,
            request_date=request_date,
            sales_unit=item.get("unit"),
            iplan=i_plan,
            item_status_en=IPlanOrderItemStatus.ITEM_CREATED.value,
            item_status_th=IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
                "Item Created"
            ),
        )
        item_parts.append(item_part)

    return item_parts


# TODO: please check this method, status?
def send_email(order_object, status, manager):
    order_line = list(OrderLines.objects.filter(order_id=order_object.id))
    order_line.sort(key=lambda line: int(line.item_no))

    data = [
        {
            "item_no": line.item_no,
            "material_description": get_material_description_from_order_line(line),
            "qty": line.quantity,
            "sales_unit": get_sales_unit_from_order_line(line),
            "qty_ton": get_qty_ton_from_order_line(line),
            "request_delivery_date": line.request_date,
            "iplan_confirm_date": line.confirmed_date if line.confirmed_date else "",
        }
        for line in order_line
    ]
    ship_to = order_object.ship_to and order_object.ship_to.split("\n")
    sold_to = order_object.contract.sold_to
    sold_to_code = sold_to and sold_to.sold_to_code or order_object.sold_to_code
    created_by = order_object.created_by
    created_by_name = (
        created_by and (created_by.first_name + " " + created_by.last_name) or ""
    )
    template_pdf_data = {
        "order_number": order_object.order_no,
        "customer_po_number": order_object.po_no,
        "file_name": order_object.order_no if order_object.order_no else "",
        "place_of_delivery": order_object.ship_to or "",
        "payment_terms": order_object.payment_term,
        "shipping": "ส่งให้",
        "note": order_object.item_note,
        "po_no": order_object.po_no,
        "sale_org_name": get_sale_org_name_from_order(order_object),
        "so_no": order_object.so_no,
        "date_time": convert_date_time_to_timezone_asia(order_object.created_at),
        "sold_to_no_name": get_sold_to_no_name(sold_to_code),
        "sold_to_address": get_address_from_order(order_object, "AG"),
        "ship_to_no_name": ship_to and ship_to[0] or "",
        "ship_to_address": ship_to[1] if ship_to and len(ship_to) == 2 else "",
        "payment_method_name": get_payment_method_name_from_order(order_object),
        "contract_no_name": get_contract_no_name_from_order(order_object),
        "remark_order_info": get_order_remark_order_info(order_object),
        "created_by": created_by_name,
        "data": data,
        "file_name_pdf": "Example",
        "print_date_time": get_date_time_now_timezone_asia(),
    }
    template_data = {
        "order_number": order_object.order_no or order_object.eo_no,
        "customer_po_number": order_object.po_no,
        "file_name": order_object.order_no if order_object.order_no else "",
        "payment_terms": order_object.payment_term,
        "shipping": "ส่งให้",
        "note": order_object.item_note,
    }
    pdf = html_to_pdf(template_pdf_data, "header.html", "content.html")
    manager.scgp_po_upload_send_mail(
        "scg.email",
        [
            "trangnn@smartosc.com",
            "anastueb@scg.com",
            "testeo-seo972@yopmail.com",
            "testeo-eo@yopmail.com",
        ],
        template_data,
        f"{get_stands_for_company(order_object)} Order submitted : {get_sold_to_no_name(sold_to_code, True)}",
        "index.html",
        pdf,
        None,
    )


def mock_request_date(order):
    import calendar

    from dateutil.relativedelta import relativedelta
    from django.utils import timezone

    order_lines = OrderLines.objects.filter(
        order=order,
        return_status__in=[
            IPLanResponseStatus.UNPLANNED.value.upper(),
            IPLanResponseStatus.TENTATIVE.value.upper(),
        ],
    )
    for order_line in order_lines:
        request_date = order_line.request_date or timezone.now().date()
        two_month_later = request_date + relativedelta(months=+2)
        last_day_of_target_month = calendar.monthrange(
            two_month_later.year, two_month_later.month
        )[1]
        order_line.request_date = timezone.datetime(
            year=two_month_later.year,
            month=two_month_later.month,
            day=last_day_of_target_month,
        ).date()
    OrderLines.objects.bulk_update(order_lines, ["request_date"])


def eo_upload_sync_contract(contract_id=None, contract_no=None, es26_response=None):
    try:
        contract = Contract.objects.filter(
            Q(id=contract_id) | Q(code=contract_no, code__isnull=False)
        ).first()
        contract_no = contract_no or contract.code
    except Contract.DoesNotExist:
        pass
    contract, response = call_sap_api_get_contracts_export_pis(contract_no)
    currency = ""

    try:
        response_data = response.get("data", [])
        if len(response_data) == 0:
            return list()

        response_data = response_data[0]

        # Save payment term code for contract
        update_instance_fields(
            contract,
            {
                "payment_term_key": response_data.get("pymTermKey"),
                "payment_term": response_data.get("pymTermDes"),
            },
            save=True,
        )

        condition_list = response_data.get("conditionList")
        for item in condition_list:
            if item.get("currency"):
                currency = item.get("currency")
                break
        list_items = response_data.get("contractItem", [])
        list_items_mat_group = ", ".join(
            set(filter(None, [item.get("matGroup1", None) for item in list_items]))
        )
        if es26_response:
            es26_response["contractItem"] = list_items
        contact_person_list = response_data.get("contactPerson", [])
        contact_persons = ", ".join(
            [
                f"{contact_person.get('contactPersonNo')} - {contact_person.get('contactPersonName')}"
                for contact_person in contact_person_list
            ]
            if "" not in contact_person_list
            else ""
        )
        order_text_list = response_data.get("orderText", [])
        order_text_list_data = get_data_from_order_text_list(order_text_list)
        order_header_text_data = make_order_header_text_mapping(order_text_list)
        sync_lang_from_order_text_list_or_db(order_text_list, contract)
        contract_sale_detail = {
            "distribution_channel": response_data.get("distributionChannel", ""),
            "division": response_data.get("division", ""),
            "sale_office": response_data.get("saleOffice", ""),
            "sale_group": response_data.get("saleGroup", ""),
            "bill_to": response_data.get("billTo", ""),
            "customer_no": response_data.get("customerNo", ""),
            "ship_to": response_data.get("shipTo")
            + " - "
            + response_data.get("shipToName"),
            "ship_to_name": response_data.get("shipToName"),
            "unloading_point": response_data.get("unloadingPoint"),
            "payer": response_data.get("payer"),
            "contact_person": contact_persons,
            "sales_employee": response_data.get("salesEmployee"),
            "author": response_data.get("author"),
            "end_customer": response_data.get("endCustomer"),
            "po_no": response_data.get("poNo"),
            "currency": currency,
            "incoterms_1": response_data.get("incoterms1"),
            "incoterms_2": response_data.get("incoterms2"),
            "usage": response_data.get("usage", None),
            "usage_no": response_data.get("usageNo", None),
            "prc_group1": list_items_mat_group,
        }
        contract_sale_detail = {
            **contract_sale_detail,
            **order_text_list_data,
            **order_header_text_data,
        }
        sync_contract_sale_detail(contract, contract_sale_detail)
        return contract
    except Exception as e:
        logging.error("[EO Upload] Error when sync contract : %s", str(e))
        return None
