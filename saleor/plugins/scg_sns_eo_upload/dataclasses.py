from dataclasses import dataclass


@dataclass
class ScgSnsEoUploadConfig:
    topic_arn: str
    client_id: str
    client_secret: str
    region_name: str
