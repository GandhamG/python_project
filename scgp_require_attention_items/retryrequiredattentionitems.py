from celery.utils.log import get_task_logger

from common.job.job import Job
from scgp_require_attention_items.implementations.retry_r5_required_attention_resolver import (
    retry_r5_required_attention_resolver,
)

task_logger = get_task_logger(__name__)


class RetryRequiredAttentionItems(Job):
    def run(self):
        task_logger.info(f"{self.job_type} run method invoked ")
        try:
            retry_r5_required_attention_resolver()
            task_logger.info("Executing job logic")
            return True
        except Exception as e:
            task_logger.exception(e)
            return False
