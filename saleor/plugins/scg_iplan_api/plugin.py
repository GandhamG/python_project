import requests
from django.conf import settings
from django.core.exceptions import ValidationError

from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField
from scg_checkout.graphql.enums import ContractCheckoutErrorCode

from . import PLUGIN_ID
from .dataclasses import ScgIPlanApiConfig


class IPlanAPIPlugin(BasePlugin):
    PLUGIN_ID = PLUGIN_ID
    # TODO: migrate to mulesoft_api
    DEFAULT_CONFIGURATION = [
        {"name": "url_api", "value": settings.MULESOFT_API_URL},
        {"name": "client_id", "value": settings.MULESOFT_CLIENT_ID},
        {"name": "client_secret", "value": settings.MULESOFT_CLIENT_SECRET},
    ]
    PLUGIN_NAME = "Scg i-plan API"
    # XXX: need ?
    CONFIGURATION_PER_CHANNEL = False

    CONFIG_STRUCTURE = {
        "url_api": {
            "type": ConfigurationTypeField.OUTPUT,
            "help_text": "IPlan API Data URL.",
            "label": "IPlan API Data URL",
        },
        "client_id": {
            "type": ConfigurationTypeField.OUTPUT,
            "help_text": "IPlan API Client Id.",
            "label": "IPlan API Client Id",
        },
        "client_secret": {
            "type": ConfigurationTypeField.OUTPUT,
            "help_text": "IPlan API Client Secret.",
            "label": "IPlan API Client Secret",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = ScgIPlanApiConfig(
            url_api=configuration["url_api"],
            client_id=configuration["client_id"],
            client_secret=configuration["client_secret"],
        )

    def call_api_i_plan_client(self, param, method, data, data_example, previous_value):
        headers = {
            "Content-Type": "application/json",
            "clientId": self.config.client_id,
            "clientSecret": self.config.client_secret,
        }
        url = self.config.url_api + param
        if method == "POST":
            response = requests.post(
                url, headers=headers, data=data, timeout=settings.MULESOFT_API_TIMEOUT
            ).json()
        else:
            response = requests.get(
                url, headers=headers, params=data, timeout=settings.MULESOFT_API_TIMEOUT
            ).json()

        if response.get("error", None) is not None:
            error = response.get("error", None)
            raise ValidationError(
                {
                    "i_plan": ValidationError(
                        f"Error when call iPlan: {str(error)}",
                        code=ContractCheckoutErrorCode.NOT_FOUND.value,
                    )
                }
            )

        if str(response.get("status", "200")) == "500":
            raise ValidationError(
                {
                    "i_plan": ValidationError(
                        "Error 500 when call iPlan.",
                        code=ContractCheckoutErrorCode.NOT_FOUND.value,
                    )
                }
            )

        if str(response.get("status", "200")) == "400":
            raise ValidationError(
                {
                    "i_plan": ValidationError(
                        "Error 400 when call iPlan.",
                        code=ContractCheckoutErrorCode.NOT_FOUND.value,
                    )
                }
            )

        if response.get("message", None) is not None:
            message = response.get("message", None)
            raise ValidationError(
                {
                    "i_plan": ValidationError(
                        f"Error when call iPlan: {str(message)}",
                        code=ContractCheckoutErrorCode.NOT_FOUND.value,
                    )
                }
            )

        return response
