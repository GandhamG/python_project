import ast
import calendar
import datetime
import json
import logging
from functools import reduce
from json import JSONDecodeError
from typing import Any, Dict, Optional, Union

from dateutil.relativedelta import relativedelta
from django.http import JsonResponse
from django.utils import timezone

from saleor import settings
from sap_migration.models import OrderLines
from scg_checkout.graphql.enums import (
    IPlanOrderItemStatus,
    IPLanResponseStatus,
    ProductionStatus,
)

from .enum import ChangeItemScenario
from .models import MulesoftLog, PluginConfig
from .product_group import ProductGroup


# XXX: deprecated
def load_config(config_name: str) -> Union[None, dict]:
    config = PluginConfig.objects.filter(identifier=config_name, active=True).first()

    if not config:
        return None
    dict_config = {item.get("name"): item.get("value") for item in config.configuration}

    return dict_config


def getattrd(__o: object, __key: str, default=None):
    try:
        return reduce(getattr, __key.split("."), __o)
    except AttributeError:
        return default


def dictgetattrd(__dictionary: dict, __key: str, default=None):
    return reduce(
        lambda d, key: d.get(key, default) if isinstance(d, dict) else default,
        __key.split("."),
        __dictionary,
    )


def is_field_updated(
    __o1: Union[object, Dict], __o2: Union[object, Dict], field: str
) -> bool:
    _val1 = None
    _val2 = None
    if isinstance(__o1, object):
        _val1 = getattrd(__o1, field, None)
    else:
        _val1 = dictgetattrd(__o1, field, None)

    if isinstance(__o2, object):
        _val2 = getattrd(__o2, field, None)
    else:
        _val2 = dictgetattrd(__o2, field, None)

    # in case it's falsy for both, consider it's not updated
    # For example: _val1 = "", _val2 = None => False
    if not _val1 and not _val2:
        return False

    return _val1 != _val2


def update_dict_if(condition: bool, target: dict, key: str, value: Any):
    if condition:
        target.update({key: value})


class DateHelper:
    ISO_FORMAT = "%Y-%m-%d"
    SAP_FORMAT = "%d/%m/%Y"

    @classmethod
    def iso_str_to_obj(cls, date_str):
        return datetime.datetime.strptime(date_str, cls.ISO_FORMAT).date()

    @classmethod
    def sap_str_to_obj(cls, date_str):
        return datetime.datetime.strptime(date_str, cls.SAP_FORMAT).date()

    @classmethod
    def obj_to_iso_str(cls, date_obj):
        return date_obj.strftime(cls.ISO_FORMAT)

    @classmethod
    def obj_to_sap_str(cls, date_obj):
        return date_obj.strftime(cls.SAP_FORMAT)

    @classmethod
    def iso_str_to_sap_str(cls, iso_str):
        return cls.obj_to_sap_str(cls.iso_str_to_obj(iso_str))

    @classmethod
    def sap_str_to_iso_str(cls, date_str):
        if not date_str:
            return None
        target_date = None

        try:
            target_date = datetime.datetime.strptime(date_str, cls.SAP_FORMAT).strftime(
                cls.ISO_FORMAT
            )

        except Exception:
            logging.warning(
                f"Error when convert  {date_str} from format { cls.SAP_FORMAT} to {cls.ISO_FORMAT}"
            )
        return target_date


def mock_confirm_date(request_date_str, iplan_status):
    """
    mock confirm date for iplan status `UNPLANNED,TENTATIVE`.
    (the last day of two month later)\n
    if iplan_status not in above status, return ""
    Args:
        request_date_str: string | example: 2023-02-24
        iplan_status: string
    Returns:
        confirm_date: string | example: 2023-04-30
    """

    if iplan_status and iplan_status.upper() in {
        IPLanResponseStatus.UNPLANNED.value.upper(),
        IPLanResponseStatus.TENTATIVE.value.upper(),
    }:
        if isinstance(request_date_str, datetime.date):
            request_date_str = request_date_str.strftime("%Y-%m-%d")
        # to ensure request date format is %Y-%m-%d
        request_date_str = "-".join(request_date_str.split("/")[::-1])
        request_date = DateHelper.iso_str_to_obj(request_date_str)

        two_month_later = request_date + relativedelta(months=+2)
        last_day_of_target_month = calendar.monthrange(
            two_month_later.year, two_month_later.month
        )[1]
        confirmed_date = timezone.datetime(
            year=two_month_later.year,
            month=two_month_later.month,
            day=last_day_of_target_month,
        )
        return DateHelper.obj_to_iso_str(confirmed_date)
    else:
        return None


def updateobjattr(obj, __field: str, __value: str):
    if getattr(obj, __field, None) != __value:
        setattr(obj, __field, __value)


def get_change_item_scenario(order_line: OrderLines) -> Union[ChangeItemScenario, None]:
    """
    doc: https://scgdigitaloffice.atlassian.net/wiki/spaces/EO/pages/568459342/Change+detail+in+order+item+level
    note: logic scenario only apply for CTP, so if ATP/ATP Future case return None
    """
    if order_line.item_status_en == IPlanOrderItemStatus.ITEM_CREATED.value:
        return ChangeItemScenario.SCENARIO_1

    if order_line.production_status in [
        ProductionStatus.UNALLOCATED.value,
        ProductionStatus.ALLOCATED.value,
        ProductionStatus.CONFIRMED.value,
    ]:
        return ChangeItemScenario.SCENARIO_1

    if order_line.production_status in [
        ProductionStatus.CLOSE_RUN.value,
        ProductionStatus.TRIMMED.value,
        ProductionStatus.IN_PRODUCTION.value,
    ]:
        return ChangeItemScenario.SCENARIO_2

    if order_line.production_status in [ProductionStatus.COMPLETED.value]:
        return ChangeItemScenario.SCENARIO_3

    return None


def get_item_scenario(order_line: OrderLines) -> Optional[ChangeItemScenario]:
    """
    summary:
        Return which item scenario for order line based on item_status_en
        If Item type is CTP, return scenario based on Production Status
        Else, return based on Item Status
    ref_doc: https://scgdigitaloffice.atlassian.net/wiki/spaces/EO/pages/574554744/Logic+change+detail+in+order

    doc_description: Item scenario based on item status

    Args:
        order_line (OrderLines): Order item model in db

    Returns:
        Optional[ChangeItemScenario]: ChangeItemScenario or None
    """
    atp_ctp = order_line.iplan.atp_ctp if order_line.iplan else None
    if atp_ctp == "CTP":
        return get_change_item_scenario(order_line)
    if order_line.item_status_en in [
        IPlanOrderItemStatus.ITEM_CREATED.value,
        IPlanOrderItemStatus.PLANNING_ALLOCATED_NON_CONFIRM.value,
        IPlanOrderItemStatus.PLANNING_CONFIRM.value,
    ]:
        return ChangeItemScenario.SCENARIO_1

    if order_line.item_status_en in [
        IPlanOrderItemStatus.PLANNING_CLOSE_LOOP.value,
        IPlanOrderItemStatus.PLANNING_ALLOCATED_X_TRIM.value,
        IPlanOrderItemStatus.PRODUCING.value,
    ]:
        return ChangeItemScenario.SCENARIO_2

    if order_line.item_status_en in [
        IPlanOrderItemStatus.FULL_COMMITTED_ORDER.value,
        IPlanOrderItemStatus.COMPLETED_PRODUCTION.value,
    ]:
        return ChangeItemScenario.SCENARIO_3

    return None


def is_allow_to_change_inquiry_method(order_line: OrderLines) -> bool:
    atp_ctp = order_line.iplan.atp_ctp if order_line.iplan else None
    if atp_ctp == "CTP":
        return get_change_item_scenario(order_line) not in [
            ChangeItemScenario.SCENARIO_2,
            ChangeItemScenario.SCENARIO_3,
        ]
    else:
        item_status_en = order_line.item_status_en
        return item_status_en not in [
            IPlanOrderItemStatus.PARTIAL_DELIVERY.value,
            IPlanOrderItemStatus.COMPLETE_DELIVERY.value,
            IPlanOrderItemStatus.CANCEL.value,
        ]


def update_instance_field(instance, field_name, value, save=True):
    if getattr(instance, field_name) == value:
        return False

    setattr(instance, field_name, value)
    if save:
        instance.save()
    return True


def update_instance_fields(instance, field_name_to_value, save=True):
    is_updated = False
    for field_name, value in field_name_to_value.items():
        is_updated = (
            update_instance_field(instance, field_name, value, save=False) or is_updated
        )

    if not is_updated:
        return False

    if save:
        instance.save()

    return True


def parse_json_if_possible(data):
    try:
        return json.loads(data)
    except JSONDecodeError:
        logging.info(
            "Error parse_json_if_possible.body_message %s is not json format", data
        )
        return data
    except Exception:
        return data


def snake_to_camel(snake_case_string: str) -> str:
    if "_" not in snake_case_string:
        return snake_case_string
    words = snake_case_string.split("_")
    camel_case_string = words[0] + "".join(word.capitalize() for word in words[1:])
    return camel_case_string


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


# TODO:  common method
def is_valid_product_group(requested_groups, validation_list):
    if requested_groups:
        if not set(requested_groups).intersection(validation_list):
            return True
    return False


def format_sap_decimal_values_for_report(value):
    """quantity format values to support 3 decimal places when sales unit is RM
    or TON  , if qty is an integer  will show integer itself"""
    decimal_value = float(value)
    return int(decimal_value) if decimal_value.is_integer() else f"{decimal_value:.3f}"


def deserialize_data(str_json_data):
    json_data = parse_json_if_possible(str_json_data)
    if not isinstance(json_data, str):
        return json_data
    return ast.literal_eval(str_json_data)


"""
This flag determines if mulesoft api log saving has to happen based on
thread local approach or by invoking rest end point approach
"""
thread_local_based_api_logging_enabled = None


def is_thread_local_based_api_log_capturing_enabled():
    return thread_local_based_api_logging_enabled


def set_thread_local_based_api_log_capturing_enabled():
    global thread_local_based_api_logging_enabled
    thread_local_based_api_logging_enabled = (
        settings.MULESOFT_API_LOGGING_VIA_THREAD_LOCAL_ENABLE
    )


def save_mulesoft_api_log_entry(filter_values, params):
    log = None
    if filter_values:
        log = MulesoftLog.objects.filter(**filter_values).order_by("created_at").last()
        if not log:
            logging.error(
                f"Error log mulesoft api (not found) {filter_values} / {params}"
            )
            return log, JsonResponse({"error": "Error log mulesoft api (not found)"})
        [setattr(log, k, v) for k, v in params.items() if k != "filter"]
        log.save()
    else:
        # create log
        log = MulesoftLog.objects.create(**params)
    return log, None


def format_sap_decimal_values_for_pdf(value):
    """format_sap_decimal_values_for_pdf : if the netWeightTon is < 0 or None from sap  pdf will show Blank
    otherwise showing in 3 decimal point"""
    if value:
        return f"{value:.3f}" if value > 0 else ""
    return ""


def net_price_calculation(product_group, quantity, price_per_unit, weight):
    if product_group in ProductGroup.get_product_group_1().value:
        return round((quantity * price_per_unit * weight), 2)
    else:
        return round((quantity * price_per_unit), 2)


def update_instance_fields_from_dic(instance, d):
    for attr, value in d.items():
        setattr(instance, attr, value)


def add_is_not_ref_to_es_25_res(sap_orders, sap_order_items):
    sd_doc_map = {}
    for item in sap_order_items:
        so_no = item["sdDoc"]
        if so_no not in sd_doc_map:
            is_ref_contract = item.get("contractPI", False) or item.get(
                "contractPIItemNo", False
            )
            sd_doc_map[so_no] = is_ref_contract
    for item in sap_orders:
        sd_doc = item["sdDoc"]
        if sd_doc in sd_doc_map:
            item["is_not_ref"] = not sd_doc_map[sd_doc]
