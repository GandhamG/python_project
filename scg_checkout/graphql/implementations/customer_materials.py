import base64
import logging
import os
import pandas as pd

from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import transaction
from django.db.models import Subquery

from sap_master_data import models as master_models
from sap_migration.models import CustomerMaterialMappingFileLog
from scg_checkout.error_codes import ContractCheckoutErrorCode
from scg_checkout.graphql.enums import CustomerMaterialMapping, CustomerMaterialUploadError, \
    CustomerMaterialHeaderColumn
from scg_checkout.graphql.helper import get_parent_directory
from scg_checkout.graphql.types import CustomerMaterialErrorData

EXCEL_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CUSTOMER_MATERIAL_TEMPLATE_XLSX_FILE_NAME = "Template Customer Material_V1.xlsx"
CUSTOMER_MATERIAL_TEMPLATE_RELATIVE_PATH = "/templates/customer_material/"


@transaction.atomic
def import_customer_material_mappings(input_param, file_data, user):
    """
    Import Customer material by upload file excel
    All SAP Material is Material Master &
    Customer Material no data reference apart from field not being null & length
    @param input_param:
    @param file_data:
    @param user:
    @return:
    """
    sold_to_code = input_param.get("sold_to_code")
    distribution_channel = input_param.get("distribution_channel")
    sales_org = input_param.get("sale_org_code")

    file_name = validate_file_size_and_format(file_data)
    logging.info(f"[Customer Material Mapping:Upload] "
                 f" processing file : {file_name} for Sold To {sold_to_code} Sales Org. {sales_org} Distribution Channel {distribution_channel}")

    sold_to_db = master_models.SoldToChannelMaster.objects.filter(
        distribution_channel_code=distribution_channel,
        sales_organization_code=sales_org,
        sold_to_code__in=Subquery(
            master_models.SoldToMaster.objects.
            filter(sold_to_code=sold_to_code,
                   account_group_code__in=["DREP", "Z001", "ZP01"]).distinct(
                "sold_to_code").values("sold_to_code"))).first()

    if not sold_to_db:
        raise ValidationError(
            {
                "sold_to": ValidationError(
                    "Invalid Sold to / Sales org./ Distribution channel",
                    code=ContractCheckoutErrorCode.INVALID.value,
                )
            }
        )

    try:
        # TODO: Read, Validate & save data
        header_row = pd.read_excel(file_data, nrows=1)
        validate_file_header(header_row)

        customer_material_column_map = CustomerMaterialHeaderColumn().find("ALL", "")

        field_type = {col["index"]: col["type"] for col in customer_material_column_map}
        df = pd.read_excel(file_data, dtype=field_type
                           , keep_default_na=False)

        sheet_lines = df.values.tolist()

        handled_lines = []
        validation_errors = []
        error_line_data = {}
        sold_to_material_list = []
        dict_cust_materials = {}

        sap_materials_db = get_material_data_from_db(sheet_lines)

        for index, line in enumerate(sheet_lines):
            line_no = index + 2
            line_data = {f.get("field"): line[f.get("index")] for f in customer_material_column_map}

            if line in handled_lines:
                add_to_error(validation_errors, line_no, "Duplicate Row")
                error_line_data[line_no] = line_data
                continue

            errors = validate_sheet_line(
                line_no,
                line,
                sold_to_db,
                sap_materials_db,
                customer_material_column_map
            )
            if len(errors):
                validation_errors += errors
                error_line_data[line_no] = line_data
                continue

            sold_to_code = line[0].strip().zfill(CustomerMaterialMapping.SOLD_TO_CODE_LENGTH.value)
            sale_org_code = line[1].strip().zfill(CustomerMaterialMapping.SALE_ORG_LENGTH.value)
            distribution_channel_code = line[2].strip()
            customer_material_code = line[3].strip()
            sap_material_code = line[4].strip()

            sold_to_material = master_models.SoldToMaterialMaster(
                sold_to_code=sold_to_code,
                sales_organization_code=sale_org_code,
                distribution_channel_code=distribution_channel_code,
                sold_to_material_code=customer_material_code,
                material_code=sap_material_code,
            )
            # Add to created alternative material
            sold_to_material_list.append(sold_to_material)
            dict_cust_materials[customer_material_code] = sold_to_material

            # Save handled line
            handled_lines.append(line)

        if len(validation_errors):
            validation_errors = sorted(validation_errors, key=lambda x: x["line"])
            raise_validation_errors(validation_errors, error_line_data)

        # delete the existing lines
        deleted = master_models.SoldToMaterialMaster.objects.filter(distribution_channel_code=distribution_channel,
                                                                    sales_organization_code=sales_org,
                                                                    sold_to_code=sold_to_code).delete()
        logging.info(f"[Customer Material Mapping:Upload] "
                     f" Deleted Records : {deleted} for Sold To {sold_to_code} Sales Org. {sales_org} Distribution Channel {distribution_channel}")

        objs = master_models.SoldToMaterialMaster.objects.bulk_create(sold_to_material_list)
        rows = len(objs)
        logging.info(
            f"[Customer Material Master Mapping:Upload] "
            f"Saved the records to DB -  {rows} records"
        )
        # NOTE: Below code upload to S3 bucket based on which AWS environment is pointed for Local testing.
        file_log_instance = CustomerMaterialMappingFileLog.objects.create(
            file_name=file_name,
            file_path=file_data,
            uploaded_by=user,
        )
        logging.info(
            f"[Customer Material Master Mapping:Upload] "
            f"Saved the file log and completed the process' "
        )
        return True, rows
    except ValidationError as validation_error:
        transaction.set_rollback(True)
        raise validation_error
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def get_material_data_from_db(sheet_lines):
    material_codes = {line[4].strip() for line in sheet_lines}
    return master_models.MaterialMaster.objects.filter(material_code__in=material_codes).distinct(
        "material_code").in_bulk(field_name="material_code")


def validate_file_header(header):
    expected_order = CustomerMaterialHeaderColumn().property_list("title")

    if header.columns.size < CustomerMaterialMapping.SHEET_COLUMN_SIZE.value:
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


def validate_file_size_and_format(file_data):
    if file_data is None:
        raise ValidationError(
            {
                "file": ValidationError(
                    "No files have been uploaded.",
                    code=ContractCheckoutErrorCode.INVALID.value,
                )
            }
        )

    # add unique text fragment to the file name to prevent file overriding
    file_name, format = os.path.splitext(file_data._name)
    if file_data.size > CustomerMaterialMapping.MAX_UPLOAD_KB.value:
        raise ValidationError(
            {
                "file_size": ValidationError(
                    CustomerMaterialUploadError.FILE_TOO_LARGE.value,
                    code=ContractCheckoutErrorCode.INVALID.value,
                )
            }
        )
    if format != ".xlsx":
        raise ValidationError(
            {
                "file_type": ValidationError(
                    CustomerMaterialUploadError.INCORRECT_FILE_FORMAT.value,
                    code=ContractCheckoutErrorCode.INVALID.value,
                )
            }
        )
    return file_name


def validate_fields(line, field_map, line_no):
    errors = []
    for field in field_map:
        col_value = line[field.get("index")]
        title = field.get("title")
        size = field.get("width")
        if not col_value or col_value == "":
            add_to_error(errors, line_no, f"{title} Cannot be blank")
            continue
        if len(col_value) > size:
            add_to_error(errors, line_no, f"{title} exceeds maximum {size} digits")

    return errors


def add_to_error(errors, line, message):
    errors.append(
        {
            "line": line,
            "message": message,
        }
    )


def validate_sheet_line(
        line_no,
        line,
        sold_to_db,
        sap_materials_db,
        field_map
):
    """
    return list errors for each field validation
    """
    errors = validate_fields(line, field_map, line_no)

    sold_to_code = line[0].strip()
    sale_org_code = line[1].strip()
    distribution_channel_code = line[2].strip()
    sap_material_code = line[4].strip()

    if sold_to_code != "" and sold_to_db.sold_to_code != sold_to_code.zfill(
            CustomerMaterialMapping.SOLD_TO_CODE_LENGTH.value):
        add_to_error(errors, line_no, f"Invalid Sold to code")

    if sale_org_code != "" and sold_to_db.sales_organization_code != sale_org_code.zfill(
            CustomerMaterialMapping.SALE_ORG_LENGTH.value):
        add_to_error(errors, line_no, f"Invalid Sale Org.")

    if distribution_channel_code != "" and sold_to_db.distribution_channel_code != distribution_channel_code:
        add_to_error(errors, line_no, f"Invalid Distribution Channel")

    if sap_material_code != "" and sap_materials_db.get(sap_material_code) is None:
        add_to_error(errors, line_no, f"SAP Material Code does not exist in material master")

    return errors


def raise_validation_errors(validation_errors, error_line_data):
    list_error_messages = {}
    for ve in validation_errors:
        error_line = ve.get("line")
        error_message = ve.get("message")
        if not list_error_messages.get(error_line) or not isinstance(list_error_messages.get(error_line), list):
            list_error_messages[error_line] = [error_message]
        elif error_message not in list_error_messages[error_line]:
            list_error_messages[error_line].append(error_message)

    errors_response = {}
    for line in list_error_messages.keys():
        error_messages = ', '.join(list_error_messages.get(line))
        data = CustomerMaterialErrorData(**error_line_data[line])
        errors_response[line] = ValidationError(
            error_messages,
            code=ContractCheckoutErrorCode.INVALID.value,
            params={"data": data},
        )

    raise ValidationError(errors_response)


def export_customer_material_template_file(info):
    try:
        logging.info(
            f"[Customer Material Mapping: Download Template] requested by user : '{info.context.user}'"
        )
        current_directory = os.path.dirname(os.path.abspath(__file__))
        parent_directory = get_parent_directory(current_directory, 2)
        absolute_path = os.path.join(parent_directory + CUSTOMER_MATERIAL_TEMPLATE_RELATIVE_PATH,
                                     CUSTOMER_MATERIAL_TEMPLATE_XLSX_FILE_NAME)
        logging.info(
            f"[Customer Material Mapping: Download Template] file path: '{absolute_path}'"
        )
        with open(absolute_path, "rb") as template_file:
            file_contents = template_file.read()
        if file_contents:
            return CUSTOMER_MATERIAL_TEMPLATE_XLSX_FILE_NAME, EXCEL_CONTENT_TYPE, base64.b64encode(
                file_contents).decode("utf-8")
        else:
            raise FileNotFoundError(f"{CUSTOMER_MATERIAL_TEMPLATE_XLSX_FILE_NAME} File doesn't exist")
    except FileNotFoundError as error:
        logging.error(
            f"[Customer Material Mapping: Download Template] Failed with: {error}"
        )
        raise error
    except Exception as e:
        logging.error(
            f"[Customer Material Mapping] Download Template Failed with: {e}"
        )
        raise ImproperlyConfigured("Internal Server Error.")
