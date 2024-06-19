import json
import logging
import time
import uuid
from typing import Union

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from common.enum import MulesoftServiceType
from saleor.plugins.manager import get_plugins_manager
from scg_checkout.graphql.enums import ContractCheckoutErrorCode
from scgp_export.graphql.enums import IPlanEndPoint, SapEnpoint
from scgp_po_upload.graphql.enums import BeingProcessConstants

from .models import MulesoftLog
from .util.middleware.scgp_threadlocal_middleware import (
    THREAD_LOCAL_KEY_M,
    THREAD_LOCAL_KEY_METRIC,
    add_to_thread_local,
)

METRIC_NAME = "Custom/MulesoftAPI"
SERVICE_TYPE_MAPPING = {
    MulesoftServiceType.SAP.value: {
        "code": "sap",
        "name": "SAP",
    },
    MulesoftServiceType.IPLAN.value: {
        "code": "i_plan",  # change to iplan if FE support
        "name": "iPlan",
    },
}

# TODO: improve the log condition
LOG_ENDPOINT = [
    SapEnpoint.ES_17.value,
    SapEnpoint.ES_21.value,
    SapEnpoint.LMS_REPORT_GPS.value,
    SapEnpoint.LMS_REPORT.value,
    IPlanEndPoint.I_PLAN_REQUEST.value,
    IPlanEndPoint.I_PLAN_CONFIRM.value,
    IPlanEndPoint.I_PLAN_SPLIT.value,
    IPlanEndPoint.I_PLAN_UPDATE_ORDER.value,
]

INVALID_ENUM_ENDPOINTS = [
    IPlanEndPoint.I_PLAN_PLUGIN_ID.value,
    SapEnpoint.SAP_PLUGIN_ID.value,
    IPlanEndPoint.METHOD_POST.value,
    SapEnpoint.METHOD_POST.value,
    SapEnpoint.METHOD_GET.value,
]

MULESOFT_ENDPOINTS = [
    (v.name, v.value)
    for en in [SapEnpoint, IPlanEndPoint]
    for _, v in en._meta.enum.__members__.items()
    if v.name not in INVALID_ENUM_ENDPOINTS
]

MAP_METRIC_FUNCTION_NAMES = {
    SapEnpoint.ES_14.name: "ES14",
    SapEnpoint.ES_15.name: "ES15",
    SapEnpoint.ES_17.name: "ES17",
    SapEnpoint.ES_21.name: "ES21",
    SapEnpoint.ES_26.name: "ES26",
    IPlanEndPoint.I_PLAN_REQUEST.name: "iPlanRequest",
    IPlanEndPoint.I_PLAN_CONFIRM.name: "iPlanConfirm",
    IPlanEndPoint.I_PLAN_SPLIT.name: "iPlanSplit",
    IPlanEndPoint.I_PLAN_UPDATE_ORDER.name: "iPlanUpdateOrder",
}


class MulesoftApiError(Exception):
    pass


class MulesoftApiRequest:
    _instance = None
    _url: str
    _client_id: str
    _client_secret: str
    _service_type: Union[str, None] = None  # sap or iplan
    _log_options: dict = {}
    _map_endpoints: dict = {}

    @classmethod
    def instance(cls, service_type=None, **kwargs):
        """Create a single instance of config for calling Mulesoft api

        Raises:
            Exception: Config not found in DB

        Returns:
            _type_: MulesoftApiRequest
        """
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._url: str = settings.MULESOFT_API_URL
            cls._client_id: str = settings.MULESOFT_CLIENT_ID
            cls._client_secret: str = settings.MULESOFT_CLIENT_SECRET
            cls._avail_model_fields = [f.name for f in MulesoftLog._meta.get_fields()]
        cls._service_type = service_type
        cls._log_options = {
            "feature": kwargs.get("feature"),
            "order_number": kwargs.get("order_number"),
            "orderid": kwargs.get("orderid"),
            "created_at": timezone.now(),
            "contract_no": kwargs.get("contract_no"),
        }
        return cls._instance

    @classmethod
    def get_endpoint_name(cls, url):
        if not cls._url:
            cls._url = settings.MULESOFT_API_URL  # XXX: fix this
        if not cls._map_endpoints:
            cls._map_endpoints = dict(
                [(cls._url + v, k) for k, v in MULESOFT_ENDPOINTS]
            )
        name = cls._map_endpoints.get(url, None)
        if not name:
            filter_names = [
                v for k, v in cls._map_endpoints.items() if url.startswith(k)
            ]
            name = filter_names and filter_names[0] or None
        return name

    @classmethod
    def _get_headers(cls) -> dict:
        return {
            "Content-Type": "application/json",
            "clientId": cls._client_id,
            "clientSecret": cls._client_secret,
        }

    @classmethod
    def _log_request(
        cls,
        url: str = "",
        request="",
        response=None,
        exception=None,
        response_time_ms=0,
    ) -> None:
        """Log request to Mulesoft API"""
        logging.info(
            f"MulesoftApiRequest._log_request {url} [{response_time_ms} ms] exception: {exception}"
        )
        # prevent for transaction rollback
        manager = get_plugins_manager()
        _plugin = manager.get_plugin("scg.settings")
        config = _plugin.config
        if not config.enable_mulesoft_log:
            return
        log_opts = {
            k: v
            for k, v in cls._log_options.items()
            if v is not None and k in cls._avail_model_fields
        }
        data = {
            "url": url,
            "request": str(request),
            "response": response and str(response) or None,
            "response_time_ms": int(response_time_ms),
            "exception": exception and str(exception) or None,
            **log_opts,
        }
        # XXX: add metric
        created_at = data.get("created_at")
        ts = created_at and created_at.timestamp() or time.time()
        metric_val = {
            "metric_name": settings.NEW_RELIC_MULESOFT_METRIC_NAME,
            "type": "gauge",
            "value": response_time_ms,
            "timestamp": ts,
            "attributes": {
                "orderId": data.get("orderid"),
                "mulesoftapi.name": cls.get_endpoint_name(url),
                "mulesoftapi.created_at": created_at.strftime(
                    settings.NEW_RELIC_DATETIME_FORMAT
                ),
            },
        }
        add_to_thread_local(THREAD_LOCAL_KEY_METRIC, metric_val)
        metric_function_name = MAP_METRIC_FUNCTION_NAMES.get(cls.get_endpoint_name(url))
        if metric_function_name:
            contract_no = cls._log_options.get("contract_no")
            # add metric name later if needed
            metric_function_val = {
                "type": "gauge",
                "value": int(response_time_ms),  # no digits
                "timestamp": ts,
                "attributes": {
                    "function": metric_function_name,
                    "orderId": data.get("orderid"),
                },
            }
            if contract_no:
                metric_function_val["attributes"]["contract_no"] = contract_no
            add_to_thread_local(THREAD_LOCAL_KEY_METRIC, metric_function_val)
        if not cls._should_log(url):
            return
        try:
            data = json.dumps(data, cls=DjangoJSONEncoder)
            add_to_thread_local(THREAD_LOCAL_KEY_M, data)
        except Exception as e:
            logging.exception("MulesoftApiRequest._log_request", e)

    @classmethod
    def log_request_update(cls, filter: dict, values: dict) -> None:
        logging.info(
            f"MulesoftApiRequest.log_request_update filter => {filter} / update value => {values}"
        )
        try:
            manager = get_plugins_manager()
            _plugin = manager.get_plugin("scg.settings")
            config = _plugin.config
            if not config.enable_mulesoft_log:
                return
            log_opts = {
                k: v
                for k, v in values.items()
                if v is not None and k in cls._avail_model_fields
            }
            data = {
                "filter": filter,
                **log_opts,
            }
            data = json.dumps(data, cls=DjangoJSONEncoder)
            add_to_thread_local(THREAD_LOCAL_KEY_M, data)
        except Exception as e:
            logging.exception("MulesoftApiRequest.log_request_update", e)

    @classmethod
    def _build_request_data(cls, uri: str, data: dict, piID=True):
        url = cls._url + uri
        headers = cls._get_headers()
        if piID:
            data = {"piMessageId": str(uuid.uuid1().int), **data}
        return url, headers, data

    @classmethod
    def _check_error_and_raise(cls, url, response, data):
        if cls._service_type == MulesoftServiceType.CP.value:
            return cls._check_error_and_raise_for_cp(url, data, response)
        if cls._service_type == MulesoftServiceType.OTS.value:
            return cls._check_error_and_raise_for_ots(url, data, response)
        # improve this
        if cls._service_type == MulesoftServiceType.PMT.value:
            return cls._check_error_and_raise_for_pmt(url, data, response)
        if cls._service_type in [
            MulesoftServiceType.SAP.value,
            MulesoftServiceType.IPLAN.value,
        ]:
            # support for sap and iplan (the plugin version)
            return cls._check_error_and_raise_base(
                url, data, response, cls._service_type
            )
        err = response.get("error", None)
        message = response.get("message", None)
        if err or message:
            raise ValidationError(
                {
                    "mulesoft": "Error when call to Mulesoft",
                    "error": str(err),
                    "message": str(message),
                    "request": str(data),
                    "url": url,
                }
            )
        status = response.get("status", "success")
        if status != "success":
            raise ValidationError(
                {
                    "mulesoft": f"Error {status} when call to Mulesoft",
                    "request": str(data),
                    "url": url,
                }
            )

    @classmethod
    def _check_error_and_raise_for_cp(cls, url, request, response):
        message = response.get("message", "")
        if message != "Success":
            raise ValidationError(
                {
                    "mulesoft": "Error when call to Mulesoft",
                    "message": response.get("Message", ""),
                    "request": str(request),
                    "url": url,
                }
            )

    @classmethod
    def _check_error_and_raise_for_ots(cls, url, request, response):
        status = response.get("status", "")
        if status != "S":
            raise ValidationError(
                {
                    "mulesoft": "Error when call to Mulesoft",
                    "message": response.get("errors", ""),
                    "request": str(request),
                    "url": url,
                }
            )

    @classmethod
    def _check_error_and_raise_for_pmt(cls, url, request, response):
        status_code = response.get("statusCode")
        if status_code != 200:
            error_src = (
                MulesoftServiceType.PMT.value.upper()
                if response.get("result")
                else None
            )
            error_message = response.get("result", {}).get(
                "errorMessage", "Mulesoft error."
            )
            raise MulesoftApiError(
                json.dumps({"error": error_message, "error_src": error_src})
            )

    @classmethod
    def _check_error_and_raise_base(cls, url, request, response, service_type):
        service_code = SERVICE_TYPE_MAPPING.get(service_type, {}).get("code")
        service_name = SERVICE_TYPE_MAPPING.get(service_type, {}).get("name")
        error_src = response.get("error_src", "")
        error_status_codes = ["400", "401", "422", "500", "503", "504"]
        status_code = str(response.get("status", "200"))
        _url = cls._url + IPlanEndPoint.I_PLAN_SPLIT.value
        if url == _url:
            if error_src and status_code in error_status_codes:
                message = ""
                error = ""
                item_no = ""
                if response.get("payload"):
                    source_system_error_response = response.get("payload")
                    if (
                        error_src.upper() == "SAP"
                        and isinstance(source_system_error_response, list)
                        and len(source_system_error_response) > 0
                    ):
                        error = source_system_error_response[0].get("number", "")
                        message = source_system_error_response[0].get("message", "")
                        if error != BeingProcessConstants.BEING_PROCESS_CODE:
                            item_no = source_system_error_response[0].get("itemNo", "")
                    elif error_src.upper() == "IPLAN":
                        error = source_system_error_response.get("returnCode", "1")
                        message = source_system_error_response.get(
                            "returnCodeDescription", ""
                        )
                error_message = (
                    f"{item_no} - {error} - {message}"
                    if item_no != ""
                    else f"{error} - {message}"
                )
                raise ValidationError(
                    {
                        error_src: ValidationError(
                            error_message,
                            code=ContractCheckoutErrorCode.NOT_FOUND.value,
                        ),
                        "error_src": error_src,
                    }
                )

        if response.get("error", None) is not None:
            error = response.get("error", None)
            message = response.get("message", "")
            status = response.get("status", "")
            raise ValidationError(
                {
                    service_code: ValidationError(
                        f"{status} - {str(error)}: {str(message)}",
                        code=ContractCheckoutErrorCode.NOT_FOUND.value,
                    ),
                    "error_src": error_src,
                }
            )

        if status_code in error_status_codes:
            raise ValidationError(
                {
                    service_code: ValidationError(
                        f"Error {status_code} when call {service_name}.",
                        code=ContractCheckoutErrorCode.NOT_FOUND.value,
                    ),
                    "error_src": error_src,
                }
            )

        if response.get("message", None) is not None:
            message = response.get("message", None)
            if (
                service_type == MulesoftServiceType.SAP.value
                and (isinstance(message, str) and message.lower() != "success")
                or service_type == MulesoftServiceType.IPLAN.value
            ):
                raise ValidationError(
                    {
                        service_code: ValidationError(
                            f"Error when call {service_name}: {str(message)}",
                            code=ContractCheckoutErrorCode.NOT_FOUND.value,
                        ),
                        "error_src": error_src,
                    }
                )

    @classmethod
    def _should_log(cls, url: str):
        return url in [cls._url + path for path in LOG_ENDPOINT]

    @classmethod
    def request_mulesoft_get(cls, uri: str, params):
        url, headers, params = cls._build_request_data(uri, params)
        t0 = time.time()
        log_val = {
            "url": url,
            "request": params,
            "response_time_ms": 0,
        }
        try:
            response = requests.get(
                url=url,
                headers=headers,
                params=params,
                timeout=settings.MULESOFT_API_TIMEOUT,
            ).json()
            t1 = time.time()
            dt = (t1 - t0) * 1000
            # no need log response because it's too big
            # log_val["response"] = response
            cls._check_error_and_raise(url, response, params)
            return response
        except ValidationError as v_ex:
            log_val["exception"] = v_ex
            raise v_ex
        except Exception as ex:
            log_val["exception"] = ex
            raise ex
        finally:
            t1 = time.time()
            dt = (t1 - t0) * 1000
            log_val = {**log_val, "response_time_ms": dt}
            cls._log_request(**log_val)

    @classmethod
    def request_mulesoft_post(
        cls, url: str, data: dict, encode=False, log_request=True
    ):
        url, headers, params = cls._build_request_data(url, data, False)
        if encode:
            data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        else:
            data = json.dumps(data)
        t0 = time.time()
        log_val = {
            "url": url,
            "request": params,
            "response_time_ms": 0,
        }
        try:
            response = requests.post(
                url=url,
                headers=headers,
                data=data,
                timeout=settings.MULESOFT_API_TIMEOUT,
            ).json()
            t1 = time.time()
            dt = (t1 - t0) * 1000
            log_val["response"] = response
            cls._check_error_and_raise(url, response, params)
            return response
        except ValidationError as v_ex:
            log_val["exception"] = v_ex
            raise v_ex
        except Exception as ex:
            log_val["exception"] = ex
            raise ex
        finally:
            if log_request:
                t1 = time.time()
                dt = (t1 - t0) * 1000
                log_val = {**log_val, "response_time_ms": dt}
                cls._log_request(**log_val)

    @classmethod
    def request_mulesoft_patch(
        cls, url: str, data: dict, encode=False, log_request=True
    ):
        url, headers, params = cls._build_request_data(url, data, False)
        if encode:
            data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        else:
            data = json.dumps(data)
        t0 = time.time()
        log_val = {
            "url": url,
            "request": params,
            "response_time_ms": 0,
        }
        try:
            response = requests.patch(
                url=url,
                headers=headers,
                data=data,
                timeout=settings.MULESOFT_API_TIMEOUT,
            ).json()
            t1 = time.time()
            dt = (t1 - t0) * 1000
            log_val["response"] = response
            cls._check_error_and_raise(url, response, params)
            return response
        except ValidationError as v_ex:
            log_val["exception"] = v_ex
            raise v_ex
        except Exception as ex:
            log_val["exception"] = ex
            raise ex
        finally:
            if log_request:
                t1 = time.time()
                dt = (t1 - t0) * 1000
                log_val = {**log_val, "response_time_ms": dt}
                cls._log_request(**log_val)
