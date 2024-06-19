from celery.utils.log import get_task_logger

from saleor.celeryconf import app

# TODO: check import error on worker

task_logger = get_task_logger(__name__)


@app.task
def DTR_DTP_logic():
    task_logger.info("Starting cron DTR DTP logic!")
    try:
        task_logger.info("Finished cron DTR DTP logic!")
    except Exception as ex:
        task_logger.error(str(ex))
        raise ex
