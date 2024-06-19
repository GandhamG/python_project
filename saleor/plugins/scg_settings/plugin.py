from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField

from . import PLUGIN_ID
from .dataclasses import ScgSettings


class ScgSettingsPlugin(BasePlugin):
    PLUGIN_ID = PLUGIN_ID
    DEFAULT_CONFIGURATION = [
        {"name": "enable_mulesoft_log", "value": True},
        {"name": "enable_upload_user", "value": True},
        {"name": "enable_target_qty_decimal_round_up", "value": True},
        {"name": "enable_alt_mat_outsource_feature", "value": True},
    ]
    PLUGIN_NAME = "Scg Settings"
    CONFIGURATION_PER_CHANNEL = False

    CONFIG_STRUCTURE = {
        "enable_mulesoft_log": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": "Enable Mulesoft Log.",
            "label": "Enable Mulesoft Log",
        },
        "enable_upload_user": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": "Enable Upload User.",
            "label": "Enable Upload User",
        },
        "enable_target_qty_decimal_round_up": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": "Enable IPlan qty decimals round-up",
            "label": "Enable IPlan qty decimals round-up",
        },
        "enable_alt_mat_outsource_feature": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": "Enable Alt Mat Outsource Feature",
            "label": "Enable Alt Mat Outsource Feature",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = ScgSettings(
            enable_mulesoft_log=configuration["enable_mulesoft_log"],
            enable_upload_user=configuration["enable_upload_user"],
            enable_target_qty_decimal_round_up=configuration[
                "enable_target_qty_decimal_round_up"
            ],
            enable_alt_mat_outsource_feature=configuration[
                "enable_alt_mat_outsource_feature"
            ],
        )
