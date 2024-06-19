import time

from celery.utils.log import get_task_logger

from saleor.celeryconf import app
from scg_checkout.contract_order_update import delete_contract_order_drafts
from scg_checkout.graphql.implementations.orders import sync_i_plan_data, sync_sap_data

task_logger = get_task_logger(__name__)


@app.task
def remove_all_contract_order_drafts():
    task_logger.info("Starting cron remove all contract order drafts")
    try:
        delete_contract_order_drafts()
        task_logger.info("Task finished!")
    except Exception as ex:
        task_logger.error(str(ex))
        raise ex


@app.task
def sync_orders_data():
    """
    Update order with data from SAP ES38
    @return:
    """
    task_logger.info("Starting cron update orders status (SAP ES-38)")
    try:
        sync_sap_data()
        task_logger.info("Finished cron update orders status (SAP ES-38)!")
    except Exception as ex:
        task_logger.error(str(ex))
        raise ex


@app.task
def sync_orders_data_iplan():
    """
    Update order with data from iPlan YT-65218
    @return:
    """
    task_logger.info("Starting cron update orders status (iPlan YT-65218)")
    try:
        t0 = time.time()
        sync_i_plan_data()
        t1 = time.time()
        dt = (t1 - t0) * 1000
        task_logger.info(
            "Finished cron update orders status (iPlan YT-65218)! Processed Time: %d ms"
            % dt
        )
    except Exception as ex:
        task_logger.error(str(ex))
        raise ex
