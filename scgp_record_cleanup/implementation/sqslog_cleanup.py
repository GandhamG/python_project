import logging

from celery.utils.log import get_task_logger
from django.utils import timezone

from common.job.jobname import JobName
from common.models import MulesoftLog
from saleor import settings
from sap_migration.models import SqsLog

task_logger = get_task_logger(__name__)

CLEAR_MULES_SOFT_LOG_DATE_RANGE = settings.CLEAR_MULES_SOFT_LOG_DATE_RANGE
CLEAR_SQS_LOG_DATE_RANGE = settings.CLEAR_SQS_LOG_DATE_RANGE


def cleanup(job_type):
    logging.info(f"{job_type} cleanup ")
    try:
        if job_type == JobName.CLEANUP_SQSLOG.value:
            days_range = timezone.now() - timezone.timedelta(
                days=CLEAR_SQS_LOG_DATE_RANGE
            )
            deleted_count = SqsLog.objects.filter(created_at__lt=days_range).delete()
            logging.info(
                f"Successfully deleted {deleted_count} records. job type: {job_type}"
            )
        elif job_type == JobName.CLEANUP_MULESOFTLOG.value:
            days_range = timezone.now() - timezone.timedelta(
                days=CLEAR_MULES_SOFT_LOG_DATE_RANGE
            )
            deleted_count = MulesoftLog.objects.filter(
                created_at__lt=days_range
            ).delete()
            logging.info(
                f"Successfully deleted {deleted_count} records. job type: {job_type}"
            )
        else:
            logging.warning(f"Unknown job type: {job_type}")
    except Exception as e:
        logging.exception(e)
