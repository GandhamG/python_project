from celery.utils.log import get_task_logger

from saleor.celeryconf import CustomLogBaseTask, app
from scgp_po_upload.implementations.po_upload import po_upload_to_sap
from scgp_po_upload.models import PoUploadFileLog, SaveToSapStatus

task_logger = get_task_logger(__name__)


@app.task
def delete_all_failed_file_logs():
    task_logger.info("Starting cron remove all failed files")
    try:
        file_logs = PoUploadFileLog.objects.filter(
            status=SaveToSapStatus.BEING_PROCESS
        ).all()
        for file_log_obj in file_logs:
            try:
                file_log_obj.file.delete()
            except Exception as e:
                task_logger.info(f"Error when delete file: {str(e)}")
        file_logs.delete()
        task_logger.info("Task finished!")
    except Exception as ex:
        task_logger.error(str(ex))
        raise ex


@app.task(name="scgp_po_upload.tasks.handle_po_upload", base=CustomLogBaseTask)
def handle_po_upload():
    task_logger.info("Starting cron po upload!")
    try:
        po_upload_to_sap()
        task_logger.info("Finished cron po upload!")
    except Exception as ex:
        task_logger.error(str(ex))
        raise ex
