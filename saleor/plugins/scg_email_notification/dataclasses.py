from dataclasses import dataclass


@dataclass
class ScgEmailNotification:
    eo_upload_fail_case_emails: str
    eo_upload_summary_emails: str
