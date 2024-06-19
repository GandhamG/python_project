import boto3
from django.conf import settings

from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField

from . import PLUGIN_ID
from .dataclasses import ScgSqsEoUploadConfig


# TODO: create a base class for all SQS plugins
class ScgSqsEoUploadPlugin(BasePlugin):
    PLUGIN_ID = PLUGIN_ID
    DEFAULT_CONFIGURATION = [
        {"name": "queue_url", "value": None},
        {"name": "client_id", "value": settings.AWS_ACCESS_KEY_ID},
        {"name": "client_secret", "value": settings.AWS_SECRET_ACCESS_KEY},
        {"name": "region_name", "value": None},
    ]
    PLUGIN_NAME = "Scg SQS EO Upload"
    CONFIGURATION_PER_CHANNEL = False

    CONFIG_STRUCTURE = {
        "queue_url": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Queue url",
            "label": "Queue url",
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
        self.config = ScgSqsEoUploadConfig(
            queue_url=configuration["queue_url"],
            client_id=configuration["client_id"],
            client_secret=configuration["client_secret"],
            region_name=configuration["region_name"],
        )

    def sqs_send_message(
        configuration,
        message=None,
        message_attributes=None,
        message_group_id=None,
        message_deduplication_id=None,
    ):
        config = configuration.config
        sqs = boto3.client(
            "sqs",
            aws_access_key_id=config.client_id,
            aws_secret_access_key=config.client_secret,
            region_name=config.region_name,
        )
        sqs.send_message(
            QueueUrl=config.queue_url,
            MessageBody=message,
            MessageAttributes=message_attributes,
            MessageGroupId=message_group_id,
            MessageDeduplicationId=message_deduplication_id,
        )

    def sqs_receive_message(configuration):
        config = configuration.config
        sqs = boto3.resource(
            "sqs",
            aws_access_key_id=config.client_id,
            aws_secret_access_key=config.client_secret,
            region_name=config.region_name,
        )
        queue_url = config.queue_url
        queue = sqs.Queue(queue_url)
        messages = queue.receive_messages(MaxNumberOfMessages=1)
        return messages
