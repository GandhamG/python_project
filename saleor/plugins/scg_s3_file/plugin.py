from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField

from . import PLUGIN_ID
from .dataclasses import ScgS3FileConfig


# TODO: create a base class for all SQS plugins
class ScgSqsPoUploadPlugin(BasePlugin):
    PLUGIN_ID = PLUGIN_ID
    DEFAULT_CONFIGURATION = [
        {"name": "queue_url", "value": None},
        {"name": "client_id", "value": None},
        {"name": "client_secret", "value": None},
        {"name": "region_name", "value": None},
        {"name": "aws_s3_bucket_name", "value": None},
        {"name": "aws_s3_access_key", "value": None},
        {"name": "aws_s3_secret_key", "value": None},
        {"name": "aws_s3_file_overwrite", "value": True},
        {"name": "aws_s3_region_name", "value": None},
    ]
    PLUGIN_NAME = "Scg SQS PO Upload"
    CONFIGURATION_PER_CHANNEL = False

    CONFIG_STRUCTURE = {
        "aws_s3_bucket_name": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "AWS s3 bucket name",
            "label": "AWS s3 bucket name",
        },
        "aws_s3_access_key": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "AWS s3 access key",
            "label": "AWS s3 access key",
        },
        "aws_s3_secret_key": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "AWS s3 secret key",
            "label": "AWS s3 secret key",
        },
        "aws_s3_region_name": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "AWS s3 Region Name",
            "label": "AWS s3 Region Name",
        },
        "aws_s3_file_overwrite": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": "AWS s3 file overwrite",
            "label": "AWS s3 file overwrite",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = ScgS3FileConfig(
            aws_s3_bucket_name=configuration["aws_s3_bucket_name"],
            aws_s3_access_key=configuration["aws_s3_access_key"],
            aws_s3_secret_key=configuration["aws_s3_secret_key"],
            aws_s3_region_name=configuration["aws_s3_region_name"],
            aws_s3_file_overwrite=configuration["aws_s3_file_overwrite"],
        )
