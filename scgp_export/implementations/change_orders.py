import copy
import datetime

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import F, Max, Q

import scg_checkout.contract_order_update as fn
from common.atp_ctp.enums import AtpCtpStatus
from common.enum import EorderingItemStatusEN, EorderingItemStatusTH
from common.helpers import mock_confirm_date
from sap_master_data import models as sap_master_data_models
from sap_migration import models as sap_migration_models
from sap_migration.graphql.enums import InquiryMethodType
from sap_migration.models import (
    ContractMaterial,
    MaterialVariantMaster,
    Order,
    OrderLineIPlan,
    OrderLines,
)
from scg_checkout.graphql.enums import IPlanOrderItemStatus
from scg_checkout.graphql.helper import (
    call_es21_get_response,
    call_i_plan_confirm_get_response,
    call_i_plan_request_get_response,
    default_param_i_plan_confirm,
    default_param_i_plan_request,
    default_param_i_plan_rollback,
    get_inquiry_method_params,
    get_non_container_materials_from_contract_materials,
    get_sold_to_partner,
    is_materials_product_group_matching,
    update_order_product_group,
)
from scg_checkout.graphql.implementations.iplan import (
    get_contract_consignment_location_from_order,
)
from scg_checkout.graphql.implementations.orders import validate_order
from scg_checkout.graphql.resolves.contracts import get_sap_contract_items
from scg_checkout.graphql.resolves.orders import call_sap_es26
from scgp_export.error_codes import ScgpExportErrorCode
from scgp_export.graphql.enums import (
    Es21Map,
    ItemCat,
    MaterialGroup,
    ScgExportOrderLineAction,
    ScgpExportOrderStatus,
    TextID,
)
from scgp_export.graphql.helper import (
    default_param_es_21_add_new_item,
    is_container,
    sync_export_order_from_es26,
)

from .orders import (
    prepare_item_header_remark,
    sync_order_prices,
    update_remaining_quantity_pi_product_for_completed_order,
    validate_lines_quantity,
)


@transaction.atomic
def add_products_to_change_export_order(order_id, products, info):
    try:
        order = validate_order(order_id)
        pi_product_ids = [product.get("pi_product", "") for product in products]
        contract = order.contract
        sales_organization_code = (
            order.sales_organization.code if order.sales_organization else None
        )
        distribution_channel_code = (
            order.distribution_channel.code if order.distribution_channel else None
        )
        sold_to_code = order.sold_to.sold_to_code
        tax_percent = fn.get_tax_percent(sold_to_code)
        channel_master = sap_master_data_models.SoldToChannelMaster.objects.filter(
            sold_to_code=sold_to_code,
            sales_organization_code=sales_organization_code,
            distribution_channel_code=distribution_channel_code,
        ).first()
        material_codes = []
        pi_product_objects = {}
        material_ids = []
        product_group = order.product_group
        contract_materials = ContractMaterial.objects.filter(id__in=pi_product_ids)
        for pi_product in contract_materials:
            pi_product_objects[str(pi_product.id)] = pi_product
            material_codes.append(pi_product.material.material_code)
            material_ids.append(pi_product.material.id)
        if not is_materials_product_group_matching(
            product_group, contract_materials, order.type
        ):
            raise ValidationError(
                {
                    "product_group": ValidationError(
                        "Please select the same product group to create an order",
                        code=ScgpExportErrorCode.PRODUCT_GROUP_ERROR.value,
                    )
                }
            )
        if product_group is None:
            contract_materials = get_non_container_materials_from_contract_materials(
                contract_materials
            )
            if contract_materials:
                product_group = contract_materials[0].mat_group_1
                update_order_product_group(order.id, product_group)
        # Get all material variant of order
        dict_material_variants = {}
        qs_material_materials = (
            MaterialVariantMaster.objects.filter(material_id__in=material_ids)
            .order_by("material_id", "id")
            .distinct("material_id")
        )
        for material_variant in qs_material_materials:
            dict_material_variants[str(material_variant.material_id)] = material_variant

        conversion_objects = (
            sap_master_data_models.Conversion2Master.objects.filter(
                material_code__in=material_codes,
                to_unit="ROL",
            )
            .order_by("material_code", "-id")
            .distinct("material_code")
            .in_bulk(field_name="material_code")
        )

        material_classification_master_objects = (
            sap_master_data_models.MaterialClassificationMaster.objects.filter(
                material_code__in=material_codes,
            )
            .distinct("material_code")
            .in_bulk(field_name="material_code")
        )

        material_sale_master_objects = (
            sap_master_data_models.MaterialSaleMaster.objects.filter(
                material_code__in=material_codes,
                sales_organization_code=sales_organization_code,
                distribution_channel_code=distribution_channel_code,
            )
            .distinct("material_code")
            .in_bulk(field_name="material_code")
        )

        bulk_create_lines = []
        max_item_no = (
            OrderLines.objects.filter(order=order)
            .aggregate(Max("item_no"))
            .get("item_no__max", 0)
        )
        max_item_no = max_item_no or 0
        item_no = int(max_item_no) + 10
        weight = 0
        for product in products:
            pi_product_id = product.get("pi_product", "")
            pi_product_object = pi_product_objects.get(str(pi_product_id), None)
            material_code = pi_product_object.material.material_code
            conversion_object = conversion_objects.get(str(material_code), None)
            material = pi_product_object.material

            if not pi_product_object:
                raise Exception(f"Contract product with id: {pi_product_id} not found")
            material_classification_master = material_classification_master_objects.get(
                str(material_code), None
            )
            material_sale_master = material_sale_master_objects.get(
                str(material_code), None
            )

            # Get variant of order line from above dict materials
            material_variant = dict_material_variants.get(str(material.id))
            if not material_variant:
                raise ValidationError(
                    {
                        "material_variant": ValidationError(
                            f"Contract material {product.get('pi_product')} don't have material variant.",
                            code=ScgpExportErrorCode.NOT_FOUND.value,
                        )
                    }
                )

            quantity = float(product.get("quantity", 0))
            if conversion_object:
                calculation = conversion_object.calculation
                weight = float(calculation) / 1000

            if order.status not in (
                ScgpExportOrderStatus.DRAFT.value,
                ScgpExportOrderStatus.PRE_DRAFT.value,
            ):
                update_remaining_quantity_pi_product_for_completed_order(
                    pi_product_object,
                    weight,
                    quantity,
                    ScgExportOrderLineAction.UPDATE.value,
                )

            net_price = weight * float(pi_product_object.price_per_unit)
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
            response = get_sap_contract_items(
                info.context.plugins.call_api_sap_client, contract_no=contract.code
            )
            order_text_list = response.get("data", [{}])[0].get("orderText", [])
            line = OrderLines(
                order=order,
                material=pi_product_object.material,
                material_code=pi_product_object.material.material_code,
                material_variant=material_variant,
                contract_material=pi_product_object,
                quantity=quantity,
                quantity_unit=pi_product_object.quantity_unit,
                weight=weight,
                weight_unit=pi_product_object.weight_unit,
                total_weight=weight * quantity,
                net_price=net_price,
                vat_percent=tax_percent * 100,
                commission_percent=pi_product_object.commission,
                commission_amount=pi_product_object.commission_amount,
                commission_unit=pi_product_object.com_unit,
                item_cat_eo=ItemCat.ZKC0.value
                if pi_product_object.material.material_group == MaterialGroup.PK00.value
                else "",
                # plant=pi_product_object.plant or "",
                # ref_pi_no=pi_product_object.item_no or "",
                delivery_tol_over=channel_master.over_delivery_tol
                if channel_master
                else None,
                delivery_tol_under=channel_master.under_delivery_tol
                if channel_master
                else None,
                delivery_tol_unlimited=False,
                roll_diameter=material_classification_master.diameter
                if material_classification_master
                else "",
                roll_core_diameter=material_classification_master.core_size
                if material_classification_master
                else "",
                roll_quantity=150,
                roll_per_pallet=300,
                pallet_size="NP",
                pallet_no="1-150",
                package_quantity=168,
                packing_list="1 ROLL x 151 PACKAGES DIMENSION (WxLxH):40'x40'x34'",
                shipping_point="",
                shipping_mark=prepare_item_header_remark(
                    order_text_list, TextID.ITEM_SHIPPING_MARK, item_no
                ).get(item_no),
                reject_reason=None,
                inquiry_method=InquiryMethodType.EXPORT.value,
                iplan=i_plan,
                material_group2=f"{material_sale_master.material_group1} - {material_sale_master.material_group1_desc}"
                if material_sale_master
                else "",
                condition_group1=pi_product_object.condition_group1,
                ref_doc=pi_product_object.contract_no or None,
                ref_doc_it=pi_product_object.item_no or None,
                draft=True,
            )
            bulk_create_lines.append(line)
            item_no += 10
        if len(bulk_create_lines):
            objs = OrderLines.objects.bulk_create(bulk_create_lines)

        invalid_quantity_line_ids = validate_lines_quantity(order.id, pi_product_ids)
        if invalid_quantity_line_ids:
            raise ValueError(
                f"Total weight of pi products {', '.join(str(line_id) for line_id in invalid_quantity_line_ids)}"
                f" are greater than total remaining "
            )

        sync_order_prices(order_id)
        return objs
    except ValidationError as e:
        transaction.set_rollback(True)
        raise e
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def change_order_add_new_items_iplan_request(order_header, list_new_items, manager):
    eo_no = order_header["eo_no"]
    param_i_plan_request = default_param_i_plan_request(eo_no)
    order_in_database = (
        sap_migration_models.Order.objects.filter(Q(eo_no=eo_no) | Q(so_no=eo_no))
        .annotate(
            sale_org_code=F("sales_organization__code"),
            sale_group_code=F("sales_group__code"),
            sold_to__sold_to_code=F("sold_to__sold_to_code"),
        )
        .first()
    )
    consignment_location = get_contract_consignment_location_from_order(
        order_in_database
    )
    for order_line_new in list_new_items:
        inquiry_method = order_line_new.get("inquiry_method", "Export")
        request_date = order_line_new["request_date"]
        inquiry_method_params = get_inquiry_method_params(inquiry_method)
        request_line = {
            "inquiryMethod": inquiry_method_params["inquiry_method"],
            "useInventory": inquiry_method_params["use_inventory"],
            "useConsignmentInventory": inquiry_method_params[
                "use_consignment_inventory"
            ],
            "useProjectedInventory": inquiry_method_params["use_projected_inventory"],
            "useProduction": inquiry_method_params["use_production"],
            "orderSplitLogic": inquiry_method_params["order_split_logic"],
            "singleSourcing": False,
            "lineNumber": order_line_new["item_no"],
            "locationCode": order_in_database.sold_to__sold_to_code.lstrip("0"),
            "productCode": order_line_new["material_code"],
            "quantity": str(order_line_new["quantity"]),
            "typeOfDelivery": "E",
            "requestType": "NEW",
            "unit": "ROL",
            "transportMethod": "Truck",
            "reATPRequired": inquiry_method_params["re_atp_required"],
            "requestDate": f"{request_date}T00:00:00.000Z",
            "consignmentOrder": False,
            "consignmentLocation": consignment_location,
            "fixSourceAssignment": order_line_new["plant"] or "",
        }
        param_i_plan_request["DDQRequest"]["DDQRequestHeader"][0][
            "DDQRequestLine"
        ].append(request_line)
        for line in param_i_plan_request["DDQRequest"]["DDQRequestHeader"][0][
            "DDQRequestLine"
        ]:
            line["DDQSourcingCategories"] = [
                {"categoryCode": order_in_database.sale_group_code or ""},
                {"categoryCode": order_in_database.sale_org_code or ""},
            ]
    return call_i_plan_request_get_response(
        manager, param_i_plan_request, order=order_in_database
    )


def change_order_add_new_item_es_21(
    order_header, list_new_items, response_i_plan, manager
):
    eo_no = order_header["eo_no"]
    order_in_database = (
        sap_migration_models.Order.objects.filter(Q(eo_no=eo_no) | Q(so_no=eo_no))
        .annotate(
            sale_org_code=F("sales_organization__code"),
            sale_group_code=F("sales_group__code"),
            sold_to__sold_to_code=F("sold_to__sold_to_code"),
        )
        .first()
    )
    contract_no = order_header["pi_no"]
    param_es_21 = default_param_es_21_add_new_item(eo_no, contract_no)
    format_dmy = "%d/%m/%Y"
    format_ymd = "%Y-%m-%d"
    contract_mat_list = sap_migration_models.ContractMaterial.objects.filter(
        contract_no=contract_no
    ).values("material_code", "mat_group_1", "plant")
    contract_mat_group = {}
    contract_plant_group = {}
    for mat in contract_mat_list:
        contract_mat_group[str(mat["material_code"])] = mat["mat_group_1"]
        contract_plant_group[str(mat["material_code"])] = mat["plant"]

    # mock request date
    plant = ""
    for line in list_new_items:
        item_number = line["item_no"]
        # Taking the plant from i_plan_response to pass it to SAP for container items.
        plant = response_i_plan[item_number]["warehouseCode"]
        if plant:
            break
    for line in list_new_items:
        item_no = line["item_no"]
        dispath_date = response_i_plan[item_no]["dispatchDate"]
        if dispath_date:
            line["request_date"] = datetime.datetime.strptime(
                dispath_date, format_ymd
            ).date()
        else:
            iplan_status = response_i_plan.get(item_no).get("status", None)
            if iplan_status:
                request_date_str = line.get("request_date").strftime(format_ymd)
                confirm_date = mock_confirm_date(request_date_str, iplan_status)
                if confirm_date:
                    line["request_date"] = datetime.datetime.strptime(
                        confirm_date, format_ymd
                    ).date()

    for order_line_new in list_new_items:
        item_no = order_line_new["item_no"]
        order_line_in = {
            "itemNo": item_no,
            "material": order_line_new.get("material_code", ""),
        }
        order_line_inx = {"itemNo": item_no, "updateflag": "I"}
        item_mat_group = contract_mat_group.get(order_line_new.get("material_code", ""))
        list_mat_group = ["K01", "K09"]
        for field_in_es21, field_name_input in Es21Map.NEW_ITEM.value.items():
            if field_name_input == "plant":
                order_line_in[field_in_es21] = (
                    response_i_plan[item_no]["warehouseCode"] or plant
                )
                order_line_inx["plant"] = True
                continue
            if field_name_input == "headerCode":
                continue
            if (
                field_name_input == "delivery_tol_unlimited"
                and item_mat_group not in list_mat_group
            ):
                if order_line_new.get(field_name_input, False):
                    order_line_in[field_in_es21] = "X"
                else:
                    order_line_in[field_in_es21] = ""
                order_line_inx[field_in_es21] = True
                continue
            if field_name_input == "request_date":
                rq_date = order_line_new.get(field_name_input).strftime(format_dmy)
                order_line_in[field_in_es21] = rq_date
                order_line_inx[field_in_es21] = True
            if field_name_input == "po_date":
                rq_date = order_line_new.get("original_request_date").strftime(
                    format_dmy
                )
                order_line_in[field_in_es21] = rq_date
                order_line_inx[field_in_es21] = True
                continue
            if order_line_new.get(field_name_input):
                order_line_in[field_in_es21] = order_line_new.get(field_name_input, "")
                order_line_inx[field_in_es21] = True
            if field_name_input == "sale_unit":
                order_line_in["salesUnit"] = (
                    "ROL"
                    if order_line_new.get("item_cat_eo", "") != ItemCat.ZKC0.value
                    else "EA"
                )
                order_line_inx["salesUnit"] = True
        order_line_in["refDoc"] = order_header["pi_no"]
        order_line_in["refDocIt"] = order_line_new.get("ref_pi_no", item_no).zfill(6)
        param_es_21["orderItemsIn"].append(order_line_in)
        param_es_21["orderItemsInx"].append(order_line_inx)
        order_schedules_in = {"itemNo": item_no.zfill(6), "scheduleLine": "0001"}
        order_schedules_inx = {
            "itemNo": item_no.zfill(6),
            "scheduleLine": "0001",
            "updateflag": "I",
            "requestDate": True,
            "requestQuantity": True,
            "confirmQuantity": True,
        }
        for field_in_es21, field_name_input in Es21Map.ORDER_SCHEDULE.value.items():
            if field_name_input == "request_date":
                request_date = order_line_new.get("request_date")
                order_schedules_in[field_in_es21] = request_date.strftime(format_dmy)
                continue
            order_schedules_in[field_in_es21] = order_line_new.get(field_name_input, "")
        order_schedules_in["confirmQty"] = (
            response_i_plan[item_no]["quantity"]
            if response_i_plan[item_no]["onHandStock"]
            else 0
        )
        param_es_21["orderSchedulesIn"].append(order_schedules_in)
        param_es_21["orderSchedulesInx"].append(order_schedules_inx)
        for field_in_es21, field_name_input in Es21Map.ORDER_TEXT.value.items():
            if order_line_new.get(field_name_input, ""):
                order_text = {
                    "itemNo": item_no.zfill(6),
                    "textId": field_in_es21,
                    "textLineList": [
                        {"textLine": order_line_new.get(field_name_input, "")}
                    ],
                }
                param_es_21["orderText"].append(order_text)

    return call_es21_get_response(manager, param_es_21, order=order_in_database)


def build_order_information_type(order_header):
    order_info_types = []
    order = sap_migration_models.Order.objects.filter(
        Q(so_no=order_header["eo_no"]) | Q(eo_no=order_header["eo_no"])
    ).first()
    if order and order.shipping_mark:
        order_info_types.append(
            {"valueType": "ShippingMarks", "value": order.shipping_mark}
        )
    if order_header.get("pi_no"):
        order_info_types.append(
            {"valueType": "ProformaInvoice", "value": order_header.get("pi_no", "")}
        )
    ship_to_code = order_header.get("ship_to", "").split("-")[0].strip()
    ship_to_partner = sap_master_data_models.SoldToPartnerAddressMaster.objects.filter(
        partner_code=ship_to_code
    ).first()
    sold_to_code = order_header.get("sold_to", "").split("-")[0].strip()
    sold_to_partner = get_sold_to_partner(sold_to_code)
    if sold_to_partner:
        sold_to_name = " ".join(
            filter(
                None,
                [
                    getattr(sold_to_partner, field, "")
                    for field in ["name1", "name2", "name3", "name4"]
                ],
            )
        )
        sold_to = f"{sold_to_code} - {sold_to_name}"

        order_info_types.append({"valueType": "SoldTo", "value": sold_to})
    if ship_to_partner and ship_to_partner.country_code:
        order_info_types.append(
            {"valueType": "Country", "value": ship_to_partner.country_code}
        )

    return order_info_types


def change_order_add_new_item_i_plan_confirm(
    response_i_plan_request,
    order_header,
    list_order_line_new,
    response_es21,
    manager,
    order=None,
):
    param_i_plan_confirm = default_param_i_plan_confirm(order_header["eo_no"])
    mapping_atp_ctp = {
        order_line["lineNumber"]: order_line
        for order_line in response_i_plan_request["DDQResponse"]["DDQResponseHeader"][
            0
        ]["DDQResponseLine"]
    }
    for order_line_new in list_order_line_new:
        item_no = order_line_new["item_no"]
        original_item_no = order_line_new["iplan_item_no"]
        if mapping_atp_ctp[original_item_no].get("onHandStock", False) == False:
            on_hand_qty = "0"
        else:
            on_hand_qty = str(response_es21[item_no].get("confirmQuantity", 0))
        confirm_line = {
            "lineNumber": item_no,
            "originalLineNumber": original_item_no,
            "onHandQuantityConfirmed": on_hand_qty,
            "unit": "ROL",
            "status": "COMMIT",
            "DDQOrderInformationType": [
                {
                    "type": "CustomInfo",
                    "DDQOrderInformationItem": build_order_information_type(
                        order_header
                    ),
                }
            ],
        }
        param_i_plan_confirm["DDQConfirm"]["DDQConfirmHeader"][0][
            "DDQConfirmLine"
        ].append(confirm_line)
    return call_i_plan_confirm_get_response(manager, param_i_plan_confirm, order=order)


def call_i_plan_rollback(manager, order_header, list_order_line_new):
    param_i_plan_rollback = default_param_i_plan_rollback(order_header["eo_no"])
    for order_line in list_order_line_new:
        confirm_line = {
            "lineNumber": order_line["item_no"],
            "originalLineNumber": order_line["item_no"],
            "status": "ROLLBACK",
            "DDQOrderInformationType": [],
        }
        param_i_plan_rollback["DDQConfirm"]["DDQConfirmHeader"][0][
            "DDQConfirmLine"
        ].append(confirm_line)
    return call_i_plan_confirm_get_response(manager, param_i_plan_rollback)


def add_special_order_line_to_iplan_data_for_call_es21(lines: list, iplan_data: dict):
    result = copy.deepcopy(iplan_data)
    for line in lines:
        result[line["item_no"]] = {
            "warehouseCode": line["plant"],
            "quantity": line["quantity"],
            "onHandStock": True,
            "dispatchDate": "",
        }
    return result


def remove_draft_order_lines(eo_no):
    order = Order.objects.filter(Q(eo_no=eo_no) | Q(so_no=eo_no)).first()
    OrderLines.all_objects.filter(Q(order=order) & Q(draft=True)).delete()


def update_item_status(order_lines):
    order_lines_to_update = []
    for order_line in order_lines:
        if not order_line.item_status_en:
            order_line.item_status_en = IPlanOrderItemStatus.ITEM_CREATED.value
            order_line.item_status_th = (
                IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
                    IPlanOrderItemStatus.ITEM_CREATED.value
                )
            )
            order_lines_to_update.append(order_line)
    OrderLines.objects.bulk_update(
        order_lines_to_update, ["item_status_en", "item_status_th"]
    )


def sync_order_line_iplan(order_line_input, order_line_iplan, iplan_response_line):
    order_type = iplan_response_line.get("orderType", "")
    order_line_iplan.atp_ctp = order_type.split(" ")[0]
    order_line_iplan.atp_ctp_detail = order_type

    if iplan_response_line.get("DDQResponseOperation"):
        response_operation = iplan_response_line.get("DDQResponseOperation")[0]
        order_line_iplan.block = response_operation.get("blockCode", "")
        order_line_iplan.run = response_operation.get("runCode", "")
        order_line_iplan.paper_machine = response_operation.get("workCentreCode", "")

    order_line_iplan.iplant_confirm_quantity = iplan_response_line.get("quantity", "")
    order_line_iplan.item_status = iplan_response_line.get("status", "")
    order_line_iplan.order_type = iplan_response_line.get("orderType", "")
    order_line_iplan.iplant_confirm_date = (
        iplan_response_line.get("dispatchDate", None)
        if iplan_response_line.get("dispatchDate", None)
        else None
    )
    order_line_iplan.plant = iplan_response_line.get("warehouseCode", "")
    order_line_iplan.on_hand_stock = iplan_response_line.get("onHandStock", "")
    order_line_iplan.item_no = iplan_response_line.get("lineNumber", "")

    # update inquiry method field
    inquiry_method_params = get_inquiry_method_params(
        order_line_input.get("inquiry_method", "Export")
    )
    order_line_iplan.inquiry_method_code = inquiry_method_params.get("inquiry_method")
    order_line_iplan.use_inventory = inquiry_method_params.get("use_inventory")
    order_line_iplan.use_consignment_inventory = inquiry_method_params.get(
        "use_consignment_inventory"
    )
    order_line_iplan.use_projected_inventory = inquiry_method_params.get(
        "use_projected_inventory"
    )
    order_line_iplan.use_production = inquiry_method_params.get("use_production")
    order_line_iplan.order_split_logic = inquiry_method_params.get("order_split_logic")
    order_line_iplan.singleSourcing = False
    order_line_iplan.re_atp_required = inquiry_method_params.get("re_atp_required")
    order_line_iplan.fix_source_assignment = order_line_input.get("plant") or ""
    order_line_iplan.request_type = "NEW"

    return order_line_iplan


def update_order_line_with_iplan_response(
    order_line, iplan_response_line, item_schedule_out
):
    iplan_on_handstock = iplan_response_line.get("onHandStock", "")
    order_line.i_plan_on_hand_stock = iplan_on_handstock
    iplan_operation = iplan_response_line.get("DDQResponseOperation", [])
    if iplan_operation:
        order_line.i_plan_operations = iplan_operation[0]
    else:
        order_line.i_plan_operations = None
    order_type = iplan_response_line.get("orderType")
    if order_type == AtpCtpStatus.ATP_ON_HAND.value:
        order_line.item_status_en = EorderingItemStatusEN.FULL_COMMITTED_ORDER.value
        order_line.item_status_th = EorderingItemStatusTH.FULL_COMMITTED_ORDER.value
    if order_type == AtpCtpStatus.ATP_FUTURE.value:
        order_line.item_status_en = EorderingItemStatusEN.PLANNING_OUTSOURCING.value
        order_line.item_status_th = EorderingItemStatusTH.PLANNING_OUTSOURCING.value
    if not iplan_on_handstock:
        order_line.assigned_quantity = 0
    if iplan_on_handstock and order_type != "CTP":
        order_line.assigned_quantity = item_schedule_out.get("confirmQuantity", 0)
    return order_line


def sync_order_line_add_new_items(
    list_new_items_iplan,
    order_header,
    i_plan_request_remapping,
    es21_remapping,
    info,
    lines,
):
    eo_no = order_header["eo_no"]
    order_db = (
        sap_migration_models.Order.objects.filter(Q(eo_no=eo_no) | Q(so_no=eo_no))
        .annotate(
            sale_org_code=F("sales_organization__code"),
            sale_group_code=F("sales_group__code"),
            sold_to__sold_to_code=F("sold_to__sold_to_code"),
        )
        .first()
    )
    remove_draft_order_lines(eo_no)
    es26_response = call_sap_es26(
        so_no=eo_no, order_id=order_db and order_db.id or None
    )
    order = sync_export_order_from_es26(es26_response)

    order_lines = OrderLines.all_objects.filter(order=order)
    dict_order_lines = {order_line.item_no: order_line for order_line in order_lines}
    # update iplan order line
    iplan_order_lines = []
    order_lines_updated = []
    for iplan_new_item in list_new_items_iplan:
        item_no = iplan_new_item["item_no"]
        order_line = dict_order_lines.get(item_no)
        iplan_response_line = i_plan_request_remapping.get(item_no)
        item_schedule_out = es21_remapping.get(item_no)

        if order_line and iplan_response_line:
            order_line_iplan = sync_order_line_iplan(
                iplan_new_item, order_line.iplan, iplan_response_line
            )
            iplan_order_lines.append(order_line_iplan)
            order_line_update = update_order_line_with_iplan_response(
                order_line, iplan_response_line, item_schedule_out
            )
            order_lines_updated.append(order_line_update)

    if order_lines_updated:
        OrderLines.objects.bulk_update(
            order_lines_updated,
            [
                "assigned_quantity",
                "i_plan_on_hand_stock",
                "i_plan_operations",
                "item_status_en",
                "item_status_th",
            ],
        )

    if iplan_order_lines:
        OrderLineIPlan.objects.bulk_update(
            iplan_order_lines,
            [
                "atp_ctp",
                "atp_ctp_detail",
                "block",
                "run",
                "paper_machine",
                "iplant_confirm_quantity",
                "item_status",
                "order_type",
                "iplant_confirm_date",
                "plant",
                "on_hand_stock",
                "item_no",
                "inquiry_method_code",
                "use_inventory",
                "use_consignment_inventory",
                "use_projected_inventory",
                "use_production",
                "split_order_item",
                "single_source",
                "re_atp_required",
                "fix_source_assignment",
                "request_type",
            ],
        )

    # update order line
    update_item_status(order_lines)
    for order_line in order_lines:
        item_no = order_line.item_no
        for line in lines:
            if item_no == line.item_no:
                order_line.inquiry_method = (
                    InquiryMethodType[line.inquiry_method].value
                    if line.inquiry_method
                    else InquiryMethodType.EXPORT.value
                )
                order_line.original_request_date = line.get("original_request_date")
                if not is_container(line.item_cat_eo):
                    order_line.confirmed_date = order_line.request_date
                order_line.shipping_mark = line.shipping_mark
    sap_migration_models.OrderLines.objects.bulk_update(
        order_lines,
        ["confirmed_date", "inquiry_method", "original_request_date", "shipping_mark"],
    )
    return order_lines
