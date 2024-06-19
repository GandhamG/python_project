import graphene


class JobName(graphene.Enum):
    RETRY_R5 = "r5_retry"
    CLEANUP_SQSLOG = "sqslog_cleanup"
    CLEANUP_MULESOFTLOG = "mulesoftlog_cleanup"
