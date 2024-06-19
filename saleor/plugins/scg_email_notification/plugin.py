from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField

from . import PLUGIN_ID
from .dataclasses import ScgEmailNotification


class ScgEmailNotificationPlugin(BasePlugin):
    PLUGIN_ID = PLUGIN_ID
    DEFAULT_CONFIGURATION = []
    PLUGIN_NAME = "Scg Email notification"
    CONFIGURATION_PER_CHANNEL = False

    CONFIG_STRUCTURE = {
        "eo_upload_fail_case_emails": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "List receiver email for eo upload fail case",
            "label": "eo upload fail case",
        },
        "eo_upload_summary_emails": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "List receiver email for eo upload summary",
            "label": "eo upload summary",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = ScgEmailNotification(
            eo_upload_fail_case_emails=configuration.get("eo_upload_fail_case_emails"),
            eo_upload_summary_emails=configuration.get("eo_upload_summary_emails"),
        )

    def get_list_email_eo_upload_fail_case(self, previous_value=None):
        return self.config.eo_upload_fail_case_emails.split(",")

    def get_list_email_eo_upload_summary(self, previous_value=None):
        return self.config.eo_upload_summary_emails.split(",")
