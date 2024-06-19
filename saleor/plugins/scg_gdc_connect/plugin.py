import requests
from django.conf import settings
from django.core.exceptions import ValidationError

from ..base_plugin import BasePlugin, ConfigurationTypeField
from . import PLUGIN_ID
from .dataclasses import ScgGdcConnectConfig


class ScgGdcPlugin(BasePlugin):
    PLUGIN_ID = PLUGIN_ID
    DEFAULT_CONFIGURATION = [
        {"name": "application_id", "value": None},
        {"name": "secret_key", "value": settings.GDC_SECRET_KEY},
        {"name": "token_url", "value": None},
        {"name": "user_data_url", "value": None},
    ]
    PLUGIN_NAME = "Scg GDC Connect"
    CONFIGURATION_PER_CHANNEL = False

    CONFIG_STRUCTURE = {
        "application_id": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "GDC Application ID.",
            "label": "Application ID",
        },
        "secret_key": {
            "type": ConfigurationTypeField.OUTPUT,
            "help_text": "GDC Secret Key.",
            "label": "Secret Key",
        },
        "token_url": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "GDC Token URL.",
            "label": "Token URL",
        },
        "user_data_url": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "GDC User Data URL.",
            "label": "User Data URL",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuration = {item["name"]: item["value"] for item in self.configuration}
        # if env is valid, use env value
        self.config = ScgGdcConnectConfig(
            application_id=configuration["application_id"],
            secret_key=settings.GDC_SECRET_KEY or configuration["secret_key"],
            token_url=configuration["token_url"],
            user_data_url=configuration["user_data_url"],
        )

    def _get_gdc_access_key(self):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "ApplicationId": self.config.application_id,
            "SecretKey": self.config.secret_key,
        }
        data = {"grant_type": "password"}
        response = requests.get(
            self.config.token_url, headers=headers, data=data
        ).json()
        return response.get("access_token", None)

    def get_user_data_by_aduser(self, username, previous_value):
        access_key = self._get_gdc_access_key()
        data = {"username": username, "referenceToken": access_key}
        response = requests.post(self.config.user_data_url, json=data).json()
        try:
            return response["responseData"][0]
        except IndexError:
            raise ValidationError("ADUSER NOT FOUND.")
        except TypeError:
            raise ValidationError("Access Key Error.")
