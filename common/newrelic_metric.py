import json
import logging
import os
from typing import Literal, Optional, Union

import requests

from sap_migration.graphql.enums import OrderType

NEW_RELIC_LICENSE_KEY = os.environ.get("NEW_RELIC_LICENSE_KEY", None)
NEW_RELIC_ENTITY_NAME = os.environ.get("NEW_RELIC_ENTITY_NAME", None)
Numeric = Union[int, float, complex]


class NewRelicMetric:
    _base_url = "https://metric-api.newrelic.com/metric/v1"
    _metric_list = []
    _api_key = NEW_RELIC_LICENSE_KEY
    _entity_name = NEW_RELIC_ENTITY_NAME

    def __init__(self) -> None:
        self._metric_list = []

    def _get_headers(self):
        return {
            "Api-Key": self._api_key,
            "Content-Type": "application/json",
        }

    def add_metric(
        self,
        metric_name,
        value,
        timestamp,
        type="gauge",
        attributes: Union[dict, None] = None,
        **kwargs
    ):
        val = {
            "name": metric_name,
            "type": type,
            "value": value,
            "timestamp": timestamp,
            "attributes": (
                {**(attributes or {}), **{"entity.name": self._entity_name or ""}}
            ),
        }
        self._metric_list.append(val)

    def send_metric(self, *args, **kwargs):
        if not self._metric_list:
            logging.info("NewRelicMetric.send_metric: No metric to send")
            return
        if not self._api_key:
            logging.warning("NewRelicMetric.send_metric: No New Relic API key")
            return
        headers = self._get_headers()
        data = [{"metrics": self._metric_list}]
        response = requests.post(self._base_url, headers=headers, data=json.dumps(data))
        if response.status_code != 202:
            logging.error(
                f"NewRelicMetric.send_metric: Failed to send metric to New Relic, status code: {response.status_code}"
            )
        self._metric_list = []


# TODO: helpers


def add_metric_process_order(
    metric_name: str,
    value: Numeric,
    timestamp: Numeric,
    function_name: Literal["SaveOrder"],
    order_type: Optional[OrderType] = OrderType.DOMESTIC,
    order_id: Optional[int] = None,
):
    from common.util.middleware.scgp_threadlocal_middleware import (
        THREAD_LOCAL_KEY_METRIC,
        add_to_thread_local,
        get_active_thread_local,
    )

    metric_function_val = {
        "metric_name": metric_name,
        "type": "gauge",
        "value": value,
        "timestamp": timestamp,
        "attributes": {
            "function": function_name,
            "orderType": order_type.value,
            "orderId": order_id,
        },
    }
    active_metrics = get_active_thread_local(THREAD_LOCAL_KEY_METRIC, [])
    for active_metric in active_metrics:
        attrs = active_metric.get("attributes", {})
        function_name = attrs.get("function") or ""
        if function_name and attrs.get("orderId", "") == order_id:
            active_metric["metric_name"] = metric_name
            active_metric["attributes"]["orderType"] = order_type.value
            metric_function_val["value"] -= active_metric.get("value", 0)
    add_to_thread_local(THREAD_LOCAL_KEY_METRIC, metric_function_val)


def force_update_attributes(target_attr_key, target_attr_value, attrs: dict) -> None:
    try:
        from common.util.middleware.scgp_threadlocal_middleware import (
            THREAD_LOCAL_KEY_METRIC,
            get_active_thread_local,
        )

        active_metrics = get_active_thread_local(THREAD_LOCAL_KEY_METRIC, [])
        for active_metric in active_metrics:
            active_attrs = active_metric.get("attributes", {})
            is_updated = all(
                k in active_attrs.keys() and active_attrs.get(k) for k in attrs.keys()
            )
            if (
                active_attrs.get(target_attr_key) == target_attr_value
                and not is_updated
            ):
                active_metric["attributes"] = {**active_attrs, **attrs}
    except Exception as ex:
        logging.error(f"Error: newrelic_metric.force_update_attributes: {ex}")
