import datetime
import logging

from django.core.exceptions import ValidationError
from django.db.models import Q

from common.sap.sap_api import SapApiRequest
from sap_master_data.models import (
    SoldToChannelPartnerMaster,
    SoldToExternalMaster,
    SoldToMaster,
    SoldToMaterialMaster,
)
from sap_migration.graphql.enums import OrderType
from sap_migration.models import ContractMaterial, MaterialVariantMaster, Order
from scg_checkout.graphql.helper import is_materials_product_group_matching
from scgp_po_upload.error_codes import ScgpPoUploadErrorCode
from scgp_po_upload.graphql.enums import (
    ContractErrorMessage,
    POUploadFlag,
    SaveToSapStatus,
)
from scgp_po_upload.models import PoUploadCustomerSettings, PoUploadFileLog
from scgp_user_management.models import ScgpUser

logger = logging.getLogger(__name__)


def _validate_po_file(user, file, sold_to_code=None):
    """
    Validate PO file and mapping some field. If any error, raise ValidationError. Otherwise, return orders has mapped
    """
    validate_file_size(file, 5)
    validate_file_type(file)
    orders = validate_file_content(
        user, file, sold_to_code=sold_to_code, raise_error=True
    )
    validate_duplicate_po_for_customer_user(user, orders)
    check_po_in_progress(orders)
    validate_contract_for_not_found(orders)
    # validate_products_group(orders)
    return orders


def validate_file_type(file):
    if file is None:
        raise ValidationError(
            {
                "-": ValidationError(
                    "No files have been uploaded.",
                    code=ScgpPoUploadErrorCode.INVALID.value,
                )
            }
        )
    if file.name.split(".")[-1] != "txt":
        raise ValidationError(
            {
                "-": ValidationError(
                    "Only support .txt file type. Please try again",
                    code=ScgpPoUploadErrorCode.INVALID.value,
                )
            }
        )


def validate_duplicate_po_for_customer_user(user, orders):
    if not is_customer_user(user):
        return True

    po_numbers_set = set(
        Order.objects.filter(contract__sold_to_code=orders[0].get("sold_to_code"))
        .exclude(so_no=None)
        .values_list("po_number", flat=True)
    )
    error_line = {
        str(line["line"]) for line in orders if line["po_number"] in po_numbers_set
    }
    if error_line:
        raise ValidationError(
            {
                ", ".join(error_line): ValidationError(
                    "Duplicate PO",
                    code=ScgpPoUploadErrorCode.INVALID.value,
                )
            }
        )


def is_customer_user(user):
    scgp_user = ScgpUser.objects.select_related("user_parent_group").get(user=user)
    return scgp_user.user_parent_group.code == "CUSTOMER"


def validate_file_content(user, file, sold_to_code=None, raise_error=True):
    """
    validate file content, raise ValidationError if any error and return orders
    """
    try:
        data = validate_lines(file)
        if not data:
            raise Exception()

        po_number_to_order = validate_orders(data, sold_to_code)
        validate_exists_in_db_and_convert_to_sap(po_number_to_order, user)
        if raise_error:
            raise_if_errors(data)
        return list(po_number_to_order.values())
    except ValidationError as e:
        raise e
    except Exception:
        raise ValidationError(
            {
                "-": ValidationError(
                    "Invalid Format",
                    code=ScgpPoUploadErrorCode.INVALID.value,
                )
            }
        )


def validate_lines(file):
    data = []
    for idx, line_bin in enumerate(file):
        line = line_bin.decode("utf-8").rstrip("\r\n")
        line_data = validate_line(idx, line)
        data.append(line_data)
    return data


def validate_orders(data, sold_to_code=None):
    po_number_to_order = {}
    contract_number = None
    file_sold_to_code = None
    order_items = []
    for line_data in data:
        if line_data["flag"] == POUploadFlag.HEADER:
            po_number = line_data["po_number"]
            if po_number in po_number_to_order:
                line_data["error_messages"].append("Duplicate PO No. in file")

            if (
                sold_to_code
                and sold_to_code != ""
                and line_data["sold_to_code"] != sold_to_code
            ):
                line_data["error_messages"].append("Invalid Sold To Code")

            if contract_number and line_data["contract_number"] != contract_number:
                line_data["error_messages"].append("No Multiple Contract")
            else:
                contract_number = line_data["contract_number"]

            if (
                file_sold_to_code
                and line_data["contract_number"] != contract_number
                and line_data["sold_to_code"] != file_sold_to_code
            ):
                line_data["error_messages"].append("No Multiple Contract")
            else:
                file_sold_to_code = line_data["sold_to_code"]

            po_number_to_order[po_number] = line_data
        elif line_data["flag"] == POUploadFlag.ITEM:
            order_items.append(line_data)

    for order_item in order_items:
        po_number = order_item["po_number"]
        if po_number not in po_number_to_order:
            order_item["error_messages"].append("Invalid PO Number")
        else:
            po_number_to_order[po_number].setdefault("items", []).append(order_item)

    return po_number_to_order


def validate_exists_in_db_and_convert_to_sap(po_number_to_order, user):
    # sap master source
    sap_sold_to_codes = SoldToMaster.objects.values_list("sold_to_code", flat=True)
    sap_ship_to_codes = SoldToChannelPartnerMaster.objects.filter(
        partner_role="WE",
    ).values("partner_code", "sold_to_code")

    # mapping source
    sold_to_external_masters = SoldToExternalMaster.objects.values(
        "sold_to_code", "partner_function", "external_customer_code", "customer_code"
    )

    # mapping setting
    po_upload_customer_settings = PoUploadCustomerSettings.objects.select_related(
        "sold_to__sold_to_code"
    ).values(
        "sold_to__sold_to_code",
        "use_customer_master",
    )

    for _, order in po_number_to_order.items():
        need_convert_to_sap = False
        if sold_to_code := order.get("sold_to_code"):
            if sold_to_code not in sap_sold_to_codes:
                order["error_messages"].append("Invalid Sold to code")
            else:
                need_convert_to_sap = is_convert_to_sap(
                    sold_to_code, po_upload_customer_settings
                )

        if ship_to_code := order.get("ship_to_code"):
            if need_convert_to_sap:
                order["ship_to_code"] = convert_to_sap_ship_to_code(
                    sold_to_code, ship_to_code, sold_to_external_masters
                )
            if {
                "sold_to_code": sold_to_code,
                "partner_code": order["ship_to_code"],
            } not in sap_ship_to_codes:
                order["error_messages"].append("Invalid Ship to code")


def validate_line(idx, line):
    d = dict()
    d["line"] = idx + 1
    d["flag"] = line[0]
    error_messages = []

    if d["flag"] not in [flag for flag in POUploadFlag]:
        error_messages.append("Invalid Flag")

    elif d["flag"] == POUploadFlag.HEADER:
        d["po_number"] = validate_value(
            line[1:36].strip(),
            "Invalid PO Number",
            error_messages,
            required=True,
        )
        d["contract_number"] = validate_value(
            line[36:46].strip().zfill(10),
            "Invalid Contract Number",
            error_messages,
            required=True,
        )

        d["sold_to_code"] = validate_value(
            line[46:56].strip().zfill(10),
            "Invalid Sold to code",
            error_messages,
            required=True,
        )

        d["ship_to_code"] = validate_value(
            line[56:73].strip().zfill(10),
            "Invalid Ship to code",
            error_messages,
            required=True,
        )

        d["bill_to_code"] = line[73:83].strip()
        d["payer_code"] = line[83:93].strip()
        d["incoterm1"] = line[93:96].strip()
        d["incoterm2"] = line[96:124].strip()
        d["remark1"] = line[124:194].strip()
        d["remark2"] = line[194:264].strip()

    elif d["flag"] == POUploadFlag.ITEM:
        d["po_number"] = validate_value(
            line[1:36].strip(),
            "Invalid PO Number",
            error_messages,
            required=True,
        )
        d["po_item_no"] = validate_value(
            line[36:42].strip(),
            "Invalid PO Item No",
            error_messages,
            required=True,
        )
        d["sku_code"] = validate_value(
            line[42:77].strip(),
            "Invalid Material",
            error_messages,
            required=True,
        )

        d["sku_name"] = line[77:117].strip()
        d["order_quantity"] = validate_value(
            line[117:131].strip(),
            "Invalid Order Quantity",
            error_messages,
            required=True,
            cast_type="int",
        )
        d["order_unit"] = validate_value(
            line[131:134].strip(), "Invalid Order Unit", error_messages, required=True
        )
        d["delivery_date"] = validate_value(
            line[134:142].strip(),
            "Invalid Delivery Date",
            error_messages,
            required=True,
            cast_type="date",
        )
        validate_delivery_date(d["delivery_date"], error_messages)
        d["remark"] = line[142:212].strip()

    d["error_messages"] = error_messages
    return d


def validate_value(
    value, error_message, errors_messages, required=False, cast_type="str"
):
    try:
        return get_validate_value(value, required, cast_type)
    except Exception:
        errors_messages.append(error_message)
        return None


def get_validate_value(value, required=False, cast_type="str"):
    if required and not value:
        raise ValueError()

    if cast_type == "str":
        return value
    elif cast_type == "int":
        return int(value) if value else None
    elif cast_type == "date":
        return datetime.datetime.strptime(value, "%d%m%Y").date() if value else None


def raise_if_errors(data):
    errors = {}
    for line_data in data:
        if error_messages := line_data["error_messages"]:
            errors[line_data["line"]] = error_messages

    if errors:
        error_response = {
            key: ValidationError(
                ", ".join(set(value)),
                code=ScgpPoUploadErrorCode.INVALID.value,
            )
            for key, value in errors.items()
        }
        raise ValidationError(error_response)


def convert_to_sap_ship_to_code(sold_to_code, ship_to_code, sold_to_external_masters):
    for item in sold_to_external_masters:
        if (
            item["sold_to_code"] == sold_to_code
            and item["partner_function"] == "WE"
            and ship_to_code.lstrip("0") == item["external_customer_code"]
        ):
            return item["customer_code"]
    return None


def convert_to_sap_material_code(sold_to_code, material_code, sold_to_material_masters):
    for item in sold_to_material_masters:
        if (
            sold_to_code == item["sold_to_code"]
            and material_code == item["sold_to_material_code"]
        ):
            return item["material_code"]
    return material_code


def is_convert_to_sap(sold_to_code, po_upload_customer_settings):
    for item in po_upload_customer_settings:
        if (
            item["sold_to__sold_to_code"] == sold_to_code
            and item["use_customer_master"]
        ):
            return True
    return False


def validate_delivery_date(value, error_messages):
    if value and value < datetime.datetime.now().date():
        error_messages.append("Invalid delivery date ( not allows to input backdate)")


def check_po_in_progress(orders):
    po_numbers_in_file = {order["po_number"]: order["line"] for order in orders}
    po_numbers_in_queue = []
    error_response = {}
    not_in_process_values = [
        SaveToSapStatus.FAIL,
        SaveToSapStatus.SUCCESS,
        SaveToSapStatus.BEING_PROCESS,
    ]
    q_not_in_process = Q()
    for value in not_in_process_values:
        q_not_in_process |= Q(status=value)
    po_numbers_in_file_log = (
        PoUploadFileLog.objects.exclude(q_not_in_process)
        .values_list("po_numbers", flat=True)
        .exclude(po_numbers=None)
    )
    if po_numbers_in_file_log is not None:
        for po_no in po_numbers_in_file_log:
            po_numbers_in_queue.extend(po_no)
        error_response = {
            po_numbers_in_file[key]: ValidationError(
                "PO is in progress",
                code=ScgpPoUploadErrorCode.INVALID.value,
            )
            for key in po_numbers_in_file.keys()
            if key in po_numbers_in_queue
        }
        if error_response != {}:
            raise ValidationError(error_response)


def validate_contract_for_not_found(orders):
    error_response = {}
    for order in orders:
        try:
            response = SapApiRequest.call_es_14_contract_detail(
                contract_no=order.get("contract_number")
            )
        except Exception as e:
            logging.exception(
                "[PO Upload] Exception during ES14 call for contract "
                + order.get("contract_number")
                + ":"
                + str(e)
            )
            raise ValidationError(
                {
                    "-": ValidationError(
                        ContractErrorMessage.TECHNICAL_ERROR,
                        code=ScgpPoUploadErrorCode.NOT_FOUND.value,
                    )
                }
            )
        if str(response.get("status", "200")) == "500":
            raise ValidationError(
                {
                    "-": ValidationError(
                        ContractErrorMessage.TECHNICAL_ERROR,
                        code=ScgpPoUploadErrorCode.NOT_FOUND.value,
                    )
                }
            )
        error_reason = response.get("reason", None)
        # SEO-5573: ER06 UI validation is not required
        if error_reason and not error_reason.startswith(
            "Material Group is out of scope."
        ):
            if error_reason.startswith("Contract end date was on"):
                error_response = {
                    order.get("line"): ValidationError(
                        ContractErrorMessage.ERROR_CODE_MESSAGE.get(
                            "Contract end date was on"
                        ).get("message"),
                        code=ScgpPoUploadErrorCode.INVALID.value,
                    )
                }
            else:
                contract_err_msgs = [
                    key
                    for key in ContractErrorMessage.ERROR_CODE_MESSAGE
                    if key.startswith(error_reason)
                ]
                if contract_err_msgs:
                    error_response = {
                        order.get("line"): ValidationError(
                            ContractErrorMessage.ERROR_CODE_MESSAGE.get(
                                contract_err_msgs[0]
                            ).get("message"),
                            code=ScgpPoUploadErrorCode.INVALID.value,
                        )
                    }
    if error_response != {}:
        raise ValidationError(error_response)


def validate_file_size(file, max_size_mb):
    max_size = max_size_mb * 1024 * 1024  # 5MB
    file_size = file.size
    if file_size > max_size:
        logger.error(f"[PO Upload] File upload exceed {max_size_mb}MB")
        raise ValidationError(
            f"{ScgpPoUploadErrorCode.FILE_EXCEED.value} {max_size_mb}MB"
        )


def filter_material_data(material, sap_mapped_material_code_set, grade_gram_code_set):
    final_mat_list = []
    for mat in sap_mapped_material_code_set:
        material_data = material.filter(material_code=mat).first()
        grade_gram_data = material.filter(material_code=mat[:10]).first()
        if material_data:
            final_mat_list.append(material_data)
        elif grade_gram_data:
            final_mat_list.append(grade_gram_data)
        else:
            raise ValidationError(f"Invalid material code in the order: {mat}")

    return final_mat_list


def fetch_and_validate_product_group(
    order,
    sold_to_code,
    need_convert_to_sap,
    sold_to_material_masters=None,
    sap_material_codes=None,
):
    sap_mapped_material_code = []
    grade_gram_code = []
    for item in order.get("items", []):
        sku_code = item.get("sku_code")
        if need_convert_to_sap and sold_to_material_masters and sap_material_codes:
            mapped_sku_code = convert_to_sap_material_code(
                sold_to_code, sku_code, sold_to_material_masters
            )
            if mapped_sku_code in sap_material_codes:
                sap_mapped_material_code.append(mapped_sku_code)
        else:
            sap_mapped_material_code.append(sku_code)
            grade_gram_code.append(sku_code[:10])
    sap_mapped_material_code_set = set(sap_mapped_material_code)
    grade_gram_code_set = set(grade_gram_code)
    material = ContractMaterial.objects.filter(
        material_code__in=sap_mapped_material_code + grade_gram_code,
        contract_no=order.get("contract_number"),
    )
    if not material:
        raise ValidationError(
            f"Invalid material code in the order: {sap_mapped_material_code}"
        )

    final_mat_list = filter_material_data(
        material, sap_mapped_material_code_set, grade_gram_code_set
    )
    if is_materials_product_group_matching(
        None, final_mat_list, OrderType.DOMESTIC.value
    ):
        order["product_group"] = final_mat_list[0].mat_group_1
        logging.info("All ContractMaterial are in same group")
        return

    raise ValidationError("Cannot Add Multiple Product Groups to an Order")


def validate_products_group(orders):
    # mapping setting
    sap_material_codes = None
    sold_to_material_masters = None
    po_upload_customer_settings = PoUploadCustomerSettings.objects.select_related(
        "sold_to__sold_to_code"
    ).values(
        "sold_to__sold_to_code",
        "use_customer_master",
    )
    sap_material_codes = MaterialVariantMaster.objects.values_list("code", flat=True)
    sold_to_material_masters = SoldToMaterialMaster.objects.values(
        "material_code", "sold_to_material_code", "sold_to_code"
    )
    for order in orders:
        sold_to_code = order.get("sold_to_code")
        need_convert_to_sap = is_convert_to_sap(
            sold_to_code, po_upload_customer_settings
        )

        fetch_and_validate_product_group(
            order,
            sold_to_code,
            need_convert_to_sap,
            sold_to_material_masters,
            sap_material_codes,
        )
