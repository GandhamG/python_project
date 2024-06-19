from celery.utils.log import get_task_logger

from common.job.jobname import JobName
from scgp_require_attention_items.retryrequiredattentionitems import (
    RetryRequiredAttentionItems,
)

task_logger = get_task_logger(__name__)


class JobFactory:
    @staticmethod
    def get_instance(job_type):
        task_logger.info(f"invoked job: {JobName.RETRY_R5.value}")
        if job_type == JobName.RETRY_R5.value:
            return RetryRequiredAttentionItems(job_type)

        return None

    @staticmethod
    def execute_job(job):
        success = False
        try:
            initiated = job.initiate()
            if initiated:
                success = job.run()
        except Exception as e:
            job.task_logger.exception(e)
            success = False
        finally:
            job.complete(success)
            task_logger.info(f"execute_job status  f {success}")

        return success
