from dataclasses import dataclass


@dataclass
class ScgSqsUpdateOrderConfig:
    queue_url: str
    client_id: str
    client_secret: str
    region_name: str
