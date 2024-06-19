import logging
import os

from celery import Celery, Task
from celery.signals import setup_logging
from django.conf import settings

from .plugins import discover_plugins_modules

CELERY_LOGGER_NAME = "celery"


@setup_logging.connect
def setup_celery_logging(loglevel=None, **kwargs):
    """Skip default Celery logging configuration.

    Will rely on Django to set up the base root logger.
    Celery loglevel will be set if provided as Celery command argument.
    """
    if loglevel:
        logging.getLogger(CELERY_LOGGER_NAME).setLevel(loglevel)


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saleor.settings")


class CustomLogBaseTask(Task):
    """Base task to be used for some Celery tasks.

    It ensures that the task is executed within the New Relic background
    task context.
    """

    def on_success(self, *args, **kwargs):
        # prevent circular import
        from common.util.middleware.scgp_threadlocal_middleware import (
            THREAD_LOCAL_KEY_M,
            THREAD_LOCAL_KEY_METRIC,
            _thread_locals,
            clear_thread_local,
            save_metric,
            save_mulesoft_api_log,
        )

        logging.info(f"CustomLogBaseTask.on_success.task_name={self.name}")

        ######## save Mulesoft Log ########
        # get all mulesoft log from thread local and save to db
        mulesoft_log_list = getattr(_thread_locals, THREAD_LOCAL_KEY_M, None)
        save_mulesoft_api_log(mulesoft_log_list)

        ######## save New Relic metric ########
        # get all metric from thread local and save to new relic
        metric_list = getattr(_thread_locals, THREAD_LOCAL_KEY_METRIC, None)
        save_metric(metric_list)
        # clear all thread local
        clear_thread_local()


app = Celery("saleor")


app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.autodiscover_tasks(lambda: discover_plugins_modules(settings.PLUGINS))
app.autodiscover_tasks(related_name="search_tasks")
