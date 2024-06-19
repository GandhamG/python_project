import logging
from datetime import datetime, timedelta

import pandas as pd
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models import Q
from django.utils import timezone

from common.models import PmtMaterialMaster
from sap_master_data import models as master_models
from scg_checkout.error_codes import ContractCheckoutErrorCode
from scg_checkout.graphql.enums import (
    ExcelUploadHeaderColumn,
    ExcelUploadMapping,
    RealtimePartnerType,
)
from scgp_cip.dao.order_line.material_master_repo import MaterialMasterRepo
from scgp_cip.dao.order_line.material_plant_master_repo import MaterialPlantMasterRepo
from scgp_export.graphql.resolvers.orders import resolve_get_credit_limit
from scgp_po_upload.error_codes import ScgpPoUploadErrorCode
from scgp_po_upload.graphql.enums import SaveToSapStatus
from scgp_po_upload.models import PoUploadFileLog

logger = logging.getLogger(__name__)


def _validate_excel_upload_file(file, sale_org_input, distribution_channel):
    """
    Validate PO file and mapping some field. If any error, raise ValidationError. Otherwise, return orders has mapped
    """
    validate_file_size(file, 30)
    validate_file_type(file)
    validate_file_name(file.name, 30)
    rows = validate_file_data(file, sale_org_input, distribution_channel)
    return rows


def validate_file_name(file_name, days):
    if not is_valid_excel_file(file_name, days):
        logger.error("[Excel Upload] file already uploaded in last 30 days ")
        raise ValidationError("ไม่สามารถอัพโหลดไฟล์ซ้ำได้, กรุณาลองใหม่")
    else:
        return True


def is_valid_excel_file(file_name, days) -> bool:
    thirty_days_ago = timezone.now() - timedelta(days=days)
    prev_files = (
        PoUploadFileLog.objects.filter(
            created_at__gte=thirty_days_ago, file_name=file_name
        )
        .exclude(status=SaveToSapStatus.FAIL)
        .count()
    )

    return prev_files == 0


def validate_file_size(file, max_size_mb):
    max_size = max_size_mb * 1024 * 1024  # 5MB
    file_size = file.size
    if file_size > max_size:
        logger.error("[Excel Upload] File upload exceed 30 MB")
        raise ValidationError("ไฟล์มีขนาดเกิน 30 MB, กรุณาลองใหม่")


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
    if file.name.split(".")[-1] != "xlsx":
        raise ValidationError(
            {
                "-": ValidationError(
                    "รองรับไฟล์นามสกุล .xlsx เท่านั้น, กรุณาลองใหม่",
                    code=ScgpPoUploadErrorCode.INVALID.value,
                )
            }
        )


def validate_file_header(header):
    expected_order = ExcelUploadHeaderColumn().property_list("title")

    if header.columns.size < ExcelUploadMapping.SHEET_COLUMN_SIZE.value:
        raise ValidationError(
            {
                "-": ValidationError(
                    f"Invalid number of header columns. Expected order is {expected_order}",
                    code=ContractCheckoutErrorCode.INVALID.value,
                )
            }
        )

    actual_order = header.columns.tolist()
    # Validate if the actual order matches the expected order
    if actual_order != expected_order:
        raise ValidationError(
            {
                "1": ValidationError(
                    f"Invalid column headers. Expected order is {expected_order}",
                    code=ContractCheckoutErrorCode.INVALID.value,
                )
            }
        )


def add_to_error(errors, line, message):
    errors.append(
        {
            "line": line,
            "message": message,
        }
    )


def validate_file_data(file, sale_org_input, distribution_channel):
    try:
        header_row = pd.read_excel(file, nrows=1)
        validate_file_header(header_row)

        column_map = ExcelUploadHeaderColumn().find("ALL", "")

        field_type = {col["index"]: "string" for col in column_map}
        df = pd.read_excel(
            file, dtype=field_type, keep_default_na=False, skiprows=[1, 2]
        )

        sheet_lines = df.values.tolist()

        handled_lines = []
        validation_errors = []
        error_line_data = {}
        sold_to_db = get_sold_to_code_from_db(sheet_lines)
        sap_materials_db = get_material_code_from_db(sheet_lines)

        if not sheet_lines:
            sheet_lines = [["" for col in column_map]]

        for index, line in enumerate(sheet_lines):
            line_no = index + 4
            line_data = {f.get("field"): line[f.get("index")] for f in column_map}

            if line in handled_lines:
                add_to_error(validation_errors, line_no, "Duplicate Row")
                error_line_data[line_no] = line_data
                continue

            errors = validate_sheet_line(
                line_no,
                line,
                sold_to_db,
                sap_materials_db,
                column_map,
                sale_org_input,
                distribution_channel,
            )
            if len(errors):
                validation_errors += errors
                error_line_data[line_no] = line_data
                continue

            # Save handled line
            handled_lines.append(line)

        if len(validation_errors):
            validation_errors = sorted(validation_errors, key=lambda x: x["line"])
            raise_validation_errors(validation_errors, error_line_data)

        return len(handled_lines)
    except ValidationError as validation_error:
        raise validation_error
    except Exception as e:
        raise ImproperlyConfigured(e)


def is_valid_date(col_value):
    date_formats = ["%Y-%m-%d %H:%M:%S", "%d.%m.%Y"]
    date_object = None
    for date_format in date_formats:
        try:
            date_object = datetime.strptime(col_value, date_format)
            break
        except ValueError:
            continue
    return date_object


def is_valid_request_date(request_date):
    current_date = datetime.now().date()
    if request_date.date() < current_date:
        return False
    if request_date.year - current_date.year > 1:
        return False
    return True


def validate_fields(line, field_map, line_no):
    errors = []

    for field in field_map:
        col_value = line[field.get("index")]
        title = field.get("title")
        size = field.get("width")
        required = field.get("required", False)
        col_name = field.get("field")
        if col_value is not None and not isinstance(col_value, str):
            add_to_error(errors, line_no, f"{title} has an incorrect format")
            continue

        if required and (not col_value or col_value == ""):
            add_to_error(errors, line_no, f"{title} cannot be blank")
            continue

        if field.get("type") == "date":
            date_value = is_valid_date(col_value)
            if date_value:
                if not is_valid_request_date(date_value):
                    add_to_error(errors, line_no, f"Invalid {title}")
            else:
                add_to_error(errors, line_no, f"{title} has an incorrect format")

            continue

        if len(col_value) > size:
            add_to_error(errors, line_no, f"{title} exceeds maximum {size} digits")

        if col_value:
            partner = None
            if col_name == "ship_to" or col_name == "item_ship_to":
                partner = return_partner_from_db(
                    col_value, RealtimePartnerType.SHIP_TO.value
                )
                if not partner:
                    add_to_error(errors, line_no, f"Invalid {title}")
            if col_name == "bill_to":
                partner = return_partner_from_db(
                    col_value, RealtimePartnerType.BILL_TO.value
                )
                if not partner:
                    add_to_error(errors, line_no, f"Invalid {title}")
            if col_name == "payer":
                partner = return_partner_from_db(col_value, "RG")
                if not partner:
                    add_to_error(errors, line_no, f"Invalid {title}")

            if col_name == "request_quantity":
                quantity = col_value.split(".")
                if float(col_value) <= 0:
                    add_to_error(errors, line_no, f"{title} should be greater than 0")
                if (len(quantity) > 1 and len(quantity[1]) > 3) or (
                    len(quantity) > 0 and len(quantity[0]) > 13
                ):
                    add_to_error(errors, line_no, f"{title} has an incorrect format")

    return errors


def return_partner_from_db(partner_code, partner_role):
    partner_code = partner_code.zfill(ExcelUploadMapping.SOLD_TO_CODE_LENGTH.value)
    return master_models.SoldToChannelPartnerMaster.objects.filter(
        partner_code=partner_code, partner_role=partner_role
    ).first()


def validate_sheet_line(
    line_no,
    line,
    sold_to_db_dic,
    materials_db,
    field_map,
    sale_org_input,
    distribution_channel,
):
    """
    return list errors for each field validation
    """
    errors = validate_fields(line, field_map, line_no)

    sold_to_code = line[2].strip()
    sale_org_code = line[0].strip()
    material_code = line[10].strip()
    material_desc = line[11].strip()
    plant = line[14].strip()

    sold_to_code = (
        sold_to_code.zfill(ExcelUploadMapping.SOLD_TO_CODE_LENGTH.value)
        if sold_to_code
        else ""
    )
    sold_to_db = sold_to_db_dic.get(sold_to_code)

    if sold_to_code != "" and not sold_to_db:
        add_to_error(errors, line_no, "Invalid Sold to code")
    if sold_to_db and sold_to_db.customer_block:
        add_to_error(errors, line_no, "Customer Blocked")

    data_input = {"sold_to_code": sold_to_code, "sales_org_code": sale_org_input}
    credit_limit = resolve_get_credit_limit(None, data_input)
    if credit_limit.get("credit_block_status"):
        add_to_error(errors, line_no, "Credit Blocked")

    if sale_org_code != "" and sale_org_input != sale_org_code.zfill(
        ExcelUploadMapping.SALE_ORG_LENGTH.value
    ):
        add_to_error(
            errors, line_no, "Sales Organization in Excel did not match in the UI"
        )

    if material_code or material_desc:
        material = None
        if material_code != "":
            material = materials_db.get(material_code)
            if not material:
                cust_material = get_customer_material_by_code(
                    sold_to_code, material_code, sale_org_input, distribution_channel
                )
                if cust_material:
                    material = MaterialMasterRepo.get_material_by_material_code(
                        cust_material.material_code
                    )
        elif material_desc != "":
            material = get_material_by_desc(
                material_desc, sale_org_input, distribution_channel
            )

        material_sale_master = material and get_material_sale_master_from_db(
            material.material_code, sale_org_input, distribution_channel
        )
        if not material or not material_sale_master:
            add_to_error(errors, line_no, "Invalid Material")
        elif (
            material
            and material.delete_flag == "X"
            or material_sale_master
            and material_sale_master.status == "Inactive"
        ):
            add_to_error(errors, line_no, "Inactive Material")
        elif material and check_material_on_hold(material.material_code):
            add_to_error(errors, line_no, "On Hold Material")
        if material and plant:
            plant_master = MaterialPlantMasterRepo.get_plant_by_material_code_and_plant(
                material.material_code, plant
            )
            if not plant_master:
                add_to_error(errors, line_no, "Invalid Plant")

    else:
        add_to_error(errors, line_no, "Material Code/Customer Material cannot be blank")

    return errors


def check_material_on_hold(material_code):
    return PmtMaterialMaster.objects.filter(material_code=material_code, is_hold=True)


def get_customer_material_by_code(
    sold_to, material_code, sale_org, distribution_channel
):
    return master_models.SoldToMaterialMaster.objects.filter(
        sold_to_code=sold_to,
        sold_to_material_code=material_code,
        sales_organization_code=sale_org,
        distribution_channel_code=distribution_channel,
    ).first()


def get_material_by_desc(material_desc, sale_org_code, distribution_channel):
    return master_models.MaterialMaster.objects.filter(
        Q(description_en=material_desc) | Q(description_th=material_desc)
    ).first()


def raise_validation_errors(validation_errors, error_line_data):
    list_error_messages = {}
    for ve in validation_errors:
        error_line = ve.get("line")
        error_message = ve.get("message")
        if not list_error_messages.get(error_line) or not isinstance(
            list_error_messages.get(error_line), list
        ):
            list_error_messages[error_line] = [error_message]
        elif error_message not in list_error_messages[error_line]:
            list_error_messages[error_line].append(error_message)

    errors_response = {}
    for line in list_error_messages.keys():
        error_messages = ", ".join(list_error_messages.get(line))
        data = error_line_data[
            line
        ]  # CustomerMaterialErrorData(**error_line_data[line])
        errors_response[line] = ValidationError(
            error_messages,
            code=ContractCheckoutErrorCode.INVALID.value,
            params={"data": data},
        )

    raise ValidationError(errors_response)


def get_sold_to_code_from_db(sheet_lines):
    sold_to_codes = {
        line[2].strip().zfill(ExcelUploadMapping.SOLD_TO_CODE_LENGTH.value)
        for line in sheet_lines
    }
    return (
        master_models.SoldToMaster.objects.filter(sold_to_code__in=sold_to_codes)
        .distinct("sold_to_code")
        .in_bulk(field_name="sold_to_code")
    )


def get_material_code_from_db(sheet_lines):
    material_codes = {line[10].strip() for line in sheet_lines}
    return (
        master_models.MaterialMaster.objects.filter(material_code__in=material_codes)
        .distinct("material_code")
        .in_bulk(field_name="material_code")
    )


def get_material_sale_master_from_db(material_code, sale_org, distribution_channel):

    return master_models.MaterialSaleMaster.objects.filter(
        material_code=material_code,
        sales_organization_code=sale_org,
        distribution_channel_code=distribution_channel,
    ).first()
