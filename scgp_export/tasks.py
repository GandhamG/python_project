import datetime
import os
import platform

import pytz
from celery.utils.log import get_task_logger
from django.conf import settings
from django.template import Context, Template
from django.utils import timezone

from saleor.celeryconf import app
from saleor.plugins.manager import PluginsManager
from sap_master_data import models as sap_master_data_models
from sap_migration.models import Order
from scg_checkout.graphql.helper import (
    get_internal_emails_by_config,
    get_name_from_sold_to_partner_address_master,
)
from scg_checkout.graphql.resolves.contracts import (
    call_sap_api_get_contracts_export_pis,
)
from scgp_eo_upload.constants import (
    EO_UPLOAD_STATE_ERROR,
    EO_UPLOAD_STATE_RECEIVED_ORDER,
)
from scgp_eo_upload.models import EoUploadLog, EoUploadLogOrderType
from scgp_export.implementations.orders import delete_all_export_order_drafts
from scgp_export.models import EOUploadSendMailSummaryLog
from scgp_user_management.models import EmailConfigurationFeatureChoices

task_logger = get_task_logger(__name__)


@app.task
def remove_all_export_order_drafts():
    task_logger.info("Starting cron remove all export order drafts")
    try:
        delete_all_export_order_drafts()
        task_logger.info("Task finished!")
    except Exception as ex:
        task_logger.error(str(ex))
        raise ex


@app.task
def eo_upload_send_email_summary():
    task_logger.info("Starting cron task send email summary")
    mail_summary_log = EOUploadSendMailSummaryLog.objects.last()
    date_log = mail_summary_log.created_at.date()
    now = timezone.now().astimezone(pytz.timezone("Asia/Bangkok"))
    if date_log == now.date():
        task_logger.info("The email summary has been duplicated")
        return
    now = now.replace(hour=15, minute=0, second=0, microsecond=0)
    start_of_day = now - datetime.timedelta(days=1)
    log_objs = EoUploadLog.objects.filter(
        updated_at__gte=start_of_day,  # Yesterday 15:00:00
        updated_at__lt=now,  # Today 14:59:59
        is_summary_email_send=False,
        state__in=[EO_UPLOAD_STATE_ERROR, EO_UPLOAD_STATE_RECEIVED_ORDER],
    ).order_by("-updated_at")

    order_objs = _get_order_objs(log_objs)

    count_success_log_objs = 0
    count_failure_log_objs = 0
    success_items = []
    eo_upload_log_list = []
    for log_obj in log_objs:
        log_obj.is_summary_email_send = True
        eo_upload_log_list.append(log_obj)
        if log_obj.state == EO_UPLOAD_STATE_ERROR:
            count_failure_log_objs += 1
        elif log_obj.state == EO_UPLOAD_STATE_RECEIVED_ORDER:
            count_success_log_objs += 1
            order_obj = order_objs.get(log_obj.orderid)
            if not order_obj:
                continue
            sold_to_name = _get_sold_to_name_from_order(order_obj)
            ship_to_name = _get_ship_to_name_from_order(order_obj)

            item = {
                "pi_no": order_obj.contract.code if order_obj.contract else "",
                "eo_no": order_obj.eo_no or "",
                "sold_to_name": sold_to_name or "",
                "ship_to_name": ship_to_name or "",
                "port_of_discharge": order_obj.port_of_discharge or "",
                "action_type": "Create"
                if log_obj.order_type == EoUploadLogOrderType.CREATE
                else "Change",
            }
            success_items.append(item)

    context = {
        "summary_datetime_str": now.strftime("%d/%m/%Y"),
        "total_file_number": len(log_objs),
        "success_file_number": count_success_log_objs,
        "failed_file_number": count_failure_log_objs,
        "success_items": success_items if success_items != [] else None,
    }

    subject = Template(
        "[Summary - SKIC] Import EO as of {{summary_datetime_str}}"
    ).render(Context(context))

    plugins = PluginsManager(settings.PLUGINS)
    recipient_list = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.EO_UPLOAD,
        [],
        [],
        exclude_sale_org_and_product_group_filter=True,
    )
    task_logger.info(
        f"task send email summary: platform({platform.system()}), os name({os.name}) os path({os.getcwd()})"
    )
    plugins.scgp_po_upload_send_mail_when_call_api_fail(
        "scg.email",
        recipient_list=recipient_list,
        subject=subject,
        template="eo_upload_summary.html",
        template_data=context,
        cc_list=[],
    )
    EOUploadSendMailSummaryLog.objects.create(created_at=now, subject=subject)
    EoUploadLog.objects.bulk_update(eo_upload_log_list, ["is_summary_email_send"])


def _get_order_objs(log_objs) -> dict:
    order_ids = []
    for log_obj in log_objs:
        if log_obj.orderid:
            order_ids.append(log_obj.orderid)

    return (
        Order.objects.select_related("contract__sold_to")
        .filter(id__in=order_ids)
        .in_bulk()
    )


def _get_sold_to_name_from_order(order):
    contract = getattr(order, "contract", None)
    sold_to_code = getattr(contract, "sold_to_code", "")
    return get_name_from_sold_to_partner_address_master(sold_to_code)


def _get_ship_to_name_from_order(order):
    contract = getattr(order, "contract", None)
    ship_to_code = getattr(contract, "ship_to", "")
    if not ship_to_code:
        return ""
    ship_to_code_formatted = ship_to_code.lstrip("0")
    sold_to_partneraddress_names = (
        sap_master_data_models.SoldToPartnerAddressMaster.objects.filter(
            partner_code=ship_to_code
        )
        .values("name1", "name2", "name3", "name4")
        .first()
    )

    if sold_to_partneraddress_names:
        name1, name2, name3, name4 = sold_to_partneraddress_names.values()
        ship_to_name = f"{name1 or ''}{name2 or ''}{name3 or ''}{name4 or ''}"
        return f"{ship_to_code_formatted} {ship_to_name}"
    else:
        return ship_to_code_formatted


def _get_ship_to_code_and_name_from_contract(contract):
    contract, response = call_sap_api_get_contracts_export_pis(contract.code)
    ship_to_text = contract and contract.ship_to or "-"
    code, name = ship_to_text.split("-")
    return f"{code.strip()} {name.strip()}"


def _check_upload_within_15_min():
    now = timezone.now().astimezone(pytz.timezone("Asia/Bangkok"))
    time_range = [now - datetime.timedelta(minutes=15), now]
    log_objs = EoUploadLog.objects.filter(
        created_at__gte=time_range[0],
        created_at__lt=time_range[1],
        state__in=[EO_UPLOAD_STATE_ERROR, EO_UPLOAD_STATE_RECEIVED_ORDER],
    ).order_by("-created_at")

    if log_objs.exists():
        return True
    else:
        return False
