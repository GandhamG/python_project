from dataclasses import dataclass


@dataclass
class ScgSapApiClientConfig:
    url_api: str
    client_id: str
    client_secret: str
