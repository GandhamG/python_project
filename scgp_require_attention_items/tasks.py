import datetime
import logging
from collections import defaultdict

from celery.utils.log import get_task_logger
from django.conf import settings as django_settings
from django.db.models import Count, Q

from common.job.jobfactory import JobFactory
from common.job.jobname import JobName
from saleor import settings
from saleor.celeryconf import CustomLogBaseTask, app
from saleor.plugins.manager import PluginsManager, get_plugins_manager
from sap_migration import models as sap_migrations_models
from scgp_record_cleanup.implementation.sqslog_cleanup import cleanup
from scgp_user_management.models import EmailConfigurationInternal, EmailInternalMapping

# TODO: check import error on worker

task_logger = get_task_logger(__name__)

active_task_counts = defaultdict(int)


@app.task
def send_email_via_r2_and_r4():
    order_lines = (
        sap_migrations_models.OrderLines.objects.filter(
            order__distribution_channel__code="30"
        )
        .filter(Q(attention_type__icontains="R2") | Q(attention_type__icontains="R4"))
        .values("order__distribution_channel__code")
        .annotate(r2=Count("id", filter=Q(attention_type__icontains="R2")))
        .annotate(r4=Count("id", filter=Q(attention_type__icontains="R4")))
        .annotate(
            r2_r4=Count(
                "id",
                filter=(
                    Q(attention_type__icontains="R2")
                    | Q(attention_type__icontains="R4")
                ),
            )
        )
    )
    if not order_lines:
        return
    bu_and_team_of_email = EmailConfigurationInternal.objects.filter(
        require_attention=True
    ).values("bu", "team")
    kwargs_filter = Q()
    cc_list = []

    for pair_bu_and_team in bu_and_team_of_email:
        kwargs_filter |= Q(
            bu=pair_bu_and_team.get("bu"), team=pair_bu_and_team.get("team")
        )
    if kwargs_filter:
        cc_list = list(
            EmailInternalMapping.objects.filter(kwargs_filter).values_list(
                "email", flat=True
            )
        )
    cc_list.append("scgh.superuser@gmail.com")
    cc_list = list(set(cc_list))

    require_attention_url = PluginsManager(settings.PLUGINS).get_require_attention_url(
        "scg.email"
    )
    now = datetime.datetime.now()
    date_time = now.strftime("%d/%m/%Y")
    time_send = now.strftime("%H")
    if int(time_send) + 7 > 12:
        time_send = "1 pm."
    else:
        time_send = "9 am."
    subject = f"Summary required attention items as of {date_time}( {time_send})"

    try:
        message = "มีรายการติด Flag required attention {r2_r4} รายการ <br> ประกอบด้วย R2 {r2} รายการ, R4 {r4} รายการ".format(
            r2_r4=order_lines[0].get("r2_r4"),
            r2=order_lines[0].get("r2"),
            r4=order_lines[0].get("r4"),
        )
        template_data = {
            "require_attention_url": require_attention_url,
            "title": "Require Attention Items",
            "message": message,
            "date_send": date_time,
            "time_send": time_send,
        }
        manage = get_plugins_manager()
        manage.send_mail_via_attention_type(
            "scg.email",
            email=cc_list,
            template_data=template_data,
            subject=subject,
            template="send_email_require_attention.html",
            pdf_file=None,
            cc_list=cc_list,
        )
    except Exception as e:
        logging.exception(e)
        pass


@app.task(name="scgp_require_attention_items.tasks.r5_retry", base=CustomLogBaseTask)
def r5_retry():
    # prevent duplicate task from scheduler
    if not django_settings.ENABLE_RETRY_R5:
        task_logger.info("tasks.r5_retry: R5 retry is disabled, ignore")
        return
    logging.info("invoked r5_retry")

    job_type = "r5_retry"
    job = JobFactory.get_instance(job_type)
    task_logger.info("instance job")
    if job:
        task_logger.info("invoked job")
        JobFactory.execute_job(job)
    else:
        task_logger.info("Invalid job type")


@app.task
def sqslog_cleanup():
    logging.info("invoked sqslog_cleanup")
    try:
        cleanup(JobName.CLEANUP_SQSLOG.value)
    except Exception as e:
        logging.exception(e)


@app.task
def mulesoftlog_cleanup():
    logging.info("invoked mulesoftlog_cleanup")
    try:
        cleanup(JobName.CLEANUP_MULESOFTLOG.value)
    except Exception as e:
        logging.exception(e)
