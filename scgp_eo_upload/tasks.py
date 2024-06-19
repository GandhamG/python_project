from celery.utils.log import get_task_logger

from saleor.celeryconf import CustomLogBaseTask, app
from scgp_eo_upload.implementations.eo_upload import sync_eo_upload

task_logger = get_task_logger(__name__)


@app.task(name="scgp_eo_upload.tasks.task_sync_eo_upload", base=CustomLogBaseTask)
def task_sync_eo_upload():
    """Consume EO Upload from SQS

    Raises:
        ex: if error
    """
    task_logger.info("Starting cron sync eo upload")
    try:
        sync_eo_upload()
        task_logger.info("Finished cron sync eo upload!")
    except Exception as ex:
        task_logger.error(str(ex))
        raise ex
