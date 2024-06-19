import boto3
from botocore.client import Config
from botocore.endpoint import DEFAULT_TIMEOUT
from django.conf import settings

from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField

from . import PLUGIN_ID
from .dataclasses import ScgSnsPoUploadConfig


# TODO: create a base class for all Sns plugins
class ScgSnsPoUploadPlugin(BasePlugin):
    PLUGIN_ID = PLUGIN_ID
    DEFAULT_CONFIGURATION = [
        {"name": "topic_arn", "value": None},
        {"name": "client_id", "value": settings.AWS_ACCESS_KEY_ID},
        {"name": "client_secret", "value": settings.AWS_SECRET_ACCESS_KEY},
        {"name": "region_name", "value": None},
    ]
    PLUGIN_NAME = "Scg Sns PO Upload"
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
        self.config = ScgSnsPoUploadConfig(
            topic_arn=configuration["topic_arn"],
            client_id=configuration["client_id"],
            client_secret=configuration["client_secret"],
            region_name=configuration["region_name"],
        )

    def sns_send_message(
        self,
        subject=None,
        message=None,
        message_attributes=None,
        message_group_id=None,
        message_deduplication_id=None,
        connect_timeout=DEFAULT_TIMEOUT,
        read_timeout=DEFAULT_TIMEOUT,
    ):
        sns_client = boto3.client(
            "sns",
            aws_access_key_id=self.config.client_id,
            aws_secret_access_key=self.config.client_secret,
            region_name=self.config.region_name,
            config=Config(connect_timeout=connect_timeout, read_timeout=read_timeout),
        )
        response = sns_client.publish(
            TopicArn=self.config.topic_arn,
            Subject=subject,
            Message=message,
            MessageAttributes=message_attributes,
            MessageGroupId=message_group_id,
            MessageDeduplicationId=message_deduplication_id,
        )
        return response
