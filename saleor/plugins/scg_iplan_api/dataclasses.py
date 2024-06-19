from dataclasses import dataclass


@dataclass
class ScgIPlanApiConfig:
    url_api: str
    client_id: str
    client_secret: str
