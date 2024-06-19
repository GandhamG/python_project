from dataclasses import dataclass


@dataclass
class ScgGdcConnectConfig:
    application_id: str
    secret_key: str
    token_url: str
    user_data_url: str
