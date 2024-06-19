from abc import ABC, abstractmethod

from celery.utils.log import get_task_logger
from django.utils import timezone

from scgp_require_attention_items.models import JobInformation

task_logger = get_task_logger(__name__)
import threading

initiate_lock = threading.Lock()


class Job(ABC):
    def __init__(self, job_type):
        self.job_type = job_type
        self.job_information = None

    def initiate(self):
        with initiate_lock:
            self.job_information = JobInformation.objects.filter(
                is_locked=True, job_type=self.job_type
            ).first()
            if self.job_information:
                task_logger.info(
                    f"Another job of the same {self.job_type} is already running"
                )
                return False
            self.job_information, created = JobInformation.objects.get_or_create(
                job_type=self.job_type,
                defaults={
                    "is_locked": True,
                    "time": timezone.now(),
                    "status": "in-progress",
                },
            )
            task_logger.info(
                f"{self.job_information.unique_id} after validation status: {self.job_information.status}"
            )
            return True

    @abstractmethod
    def run(self):
        pass

    def complete(self, success):
        task_logger.info(f"{self.job_information.unique_id} complete method invoked ")
        task_logger.info(f"{self.job_type} complete method invoked ")
        lock = JobInformation.objects.get(
            unique_id=self.job_information.unique_id, job_type=self.job_type
        )

        if success:
            lock.delete()
            task_logger.info("Job completed")
        else:
            lock.status = "failed"
            lock.is_locked = False
            lock.save()
            task_logger.info("Job failed")
