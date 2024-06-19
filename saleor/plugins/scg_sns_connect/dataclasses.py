from dataclasses import dataclass


@dataclass
class ScgSnsConfig:
    access_key: str
    secret_key: str
    topic_url: str
    region_name: str
