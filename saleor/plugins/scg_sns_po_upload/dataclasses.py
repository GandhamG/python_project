from dataclasses import dataclass


@dataclass
class ScgSnsPoUploadConfig:
    topic_arn: str
    client_id: str
    client_secret: str
    region_name: str
