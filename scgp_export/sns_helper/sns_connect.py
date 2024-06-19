import logging

import boto3

logger = logging.getLogger(__name__)


def setup_client_sns(
    region_name,
    access_key,
    secret_key,
    topic_arn,
    message,
    subject,
    message_attribute,
    message_group_id,
    message_deduplication_id,
):
    sns = boto3.client(
        "sns",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region_name,
    )
    # XXX: message_group_id and message_deduplication_id are required for FIFO

    return sns.publish(
        TopicArn=topic_arn,
        Message=message,
        Subject=subject,
        MessageAttributes=message_attribute,
        MessageGroupId=message_group_id,
        MessageDeduplicationId=message_deduplication_id,
    )
