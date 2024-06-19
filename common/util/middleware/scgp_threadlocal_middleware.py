import concurrent.futures
import logging

from _threading_local import local

from common.helpers import (
    deserialize_data,
    save_mulesoft_api_log_entry,
    set_thread_local_based_api_log_capturing_enabled,
)
from common.newrelic_metric import NewRelicMetric

_thread_locals = local()

THREAD_LOCAL_KEY_M = "mulesoft_api_log"
THREAD_LOCAL_KEY_METRIC = "metric"


def clear_thread_local(key_name=None) -> None:
    if key_name:
        setattr(_thread_locals, key_name, None)
        return
    setattr(_thread_locals, THREAD_LOCAL_KEY_M, None)
    setattr(_thread_locals, THREAD_LOCAL_KEY_METRIC, None)


class ThreadLocalMiddleware:
    def __init__(self, get_response):
        # One-time configuration and initialization
        self.get_response = get_response
        """
        Set the threadlocal based api logging flag based on settings
        only in web context. Since thread local will not work in schedule job scenario
        """
        set_thread_local_based_api_log_capturing_enabled()

    def __call__(self, request):
        clear_thread_local()
        _thread_locals.THREAD_LOCAL_KEY_M = None
        response = self.get_response(request)
        if getattr(_thread_locals, THREAD_LOCAL_KEY_M, None):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                mulesoft_api_log_list = getattr(_thread_locals, THREAD_LOCAL_KEY_M)
                executor.submit(save_mulesoft_api_log, mulesoft_api_log_list)
        metric_list = getattr(_thread_locals, THREAD_LOCAL_KEY_METRIC, None)
        if metric_list:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                executor.submit(save_metric, metric_list)
        clear_thread_local()
        return response


def add_to_thread_local(key, value):
    """
    This method is responsible for adding a mulesoft log entry to thread local with key 'THREAD_LOCAL_KEY_M'
    where value will be a list and the log entry would be appended to this list.
    :param key:
    :param value:
    :return:
    """
    if not getattr(_thread_locals, key, None):
        setattr(_thread_locals, key, [])
    values = getattr(_thread_locals, key, None)
    values.append(value)


get_active_thread_local = lambda key, default=None: getattr(
    _thread_locals, key, default
)


def save_mulesoft_api_log(mulesoft_api_log_list):
    """
    This will be invoked after completing process of a request and this will retrieve the list of mulesoft log entries
    from thread local and will save to db
    :param mulesoft_api_log_list:
    :return:
    """
    try:
        if mulesoft_api_log_list:
            for mulesoft_api_log_str in mulesoft_api_log_list:
                mulesoft_api_log = deserialize_data(mulesoft_api_log_str)
                filter_values = mulesoft_api_log.get("filter") and mulesoft_api_log.pop(
                    "filter"
                )
                save_mulesoft_api_log_entry(filter_values, mulesoft_api_log)
    except Exception as e:
        logging.exception(
            f"Some error has occurred while saving mulesoft api log entries from thread local: {e}"
        )


def save_metric(metric_list):
    if not metric_list:
        return
    try:
        metric = NewRelicMetric()
        for metric_val in metric_list:
            mname = metric_val.get("metric_name")
            if not mname:
                logging.warning(
                    f"Metric name is not present in metric_val | {metric_val}"
                )
                continue
            # custom here
            metric.add_metric(**metric_val)
        metric.send_metric()
    except Exception as e:
        logging.exception(
            "Some error has occurred while saving metrics from thread local %s" % e
        )
