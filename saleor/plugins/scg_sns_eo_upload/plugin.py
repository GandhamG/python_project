from django.conf import settings

from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField

from . import PLUGIN_ID
from .dataclasses import ScgSnsEoUploadConfig


class ScgSnsEoUploadPlugin(BasePlugin):
    PLUGIN_ID = PLUGIN_ID
    DEFAULT_CONFIGURATION = [
        {"name": "topic_arn", "value": None},
        {"name": "client_id", "value": settings.AWS_ACCESS_KEY_ID},
        {"name": "client_secret", "value": settings.AWS_SECRET_ACCESS_KEY},
        {"name": "region_name", "value": None},
    ]
    PLUGIN_NAME = "Scg Sns EO Upload"
    CONFIGURATION_PER_CHANNEL = False

    CONFIG_STRUCTURE = {
        "topic_arn": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Topic ARN",
            "label": "Topic ARN",
        },
        "client_id": {
            "type": ConfigurationTypeField.OUTPUT,
            "help_text": "AWS Client Id",
            "label": "AWS Client Id",
        },
        "client_secret": {
            "type": ConfigurationTypeField.OUTPUT,
            "help_text": "AWS Client Secret",
            "label": "AWS Client Secret",
        },
        "region_name": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "AWS Region Name",
            "label": "AWS Region Name",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = ScgSnsEoUploadConfig(
            topic_arn=configuration["topic_arn"],
            client_id=configuration["client_id"],
            client_secret=configuration["client_secret"],
            region_name=configuration["region_name"],
        )
