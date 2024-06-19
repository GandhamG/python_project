from common.enum import MulesoftServiceType

from ..mulesoft_api import MulesoftApiRequest


class IPlanApiRequest(MulesoftApiRequest):
    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def call_yt65156_api(cls, data: dict, order=None):
        log_opts = {
            "orderid": order and order.id or None,
            "order_number": order and order.so_no or None,
        }
        return MulesoftApiRequest.instance(
            service_type=MulesoftServiceType.IPLAN.value, **log_opts
        ).request_mulesoft_post(url="sales/available-to-promise/plan", data=data)

    @classmethod
    def call_yt65156_confirm_api(cls, data: dict, order=None):
        log_opts = {
            "orderid": order and order.id or None,
            "order_number": order and order.so_no or None,
        }
        return MulesoftApiRequest.instance(
            service_type=MulesoftServiceType.IPLAN.value, **log_opts
        ).request_mulesoft_post(url="sales/available-to-promise/confirm", data=data)

    @classmethod
    def call_yt65217_api_update_order(cls, data: dict, order=None):
        log_opts = {
            "orderid": order and order.id or None,
            "order_number": order and order.so_no or None,
        }
        return MulesoftApiRequest.instance(
            service_type=MulesoftServiceType.IPLAN.value, **log_opts
        ).request_mulesoft_post(url="sales/orders/updates", data=data)
