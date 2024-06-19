from dataclasses import dataclass


@dataclass
class CognitoConnectConfig:
    client_id: str
    client_secret: str
    enable_refresh_token: bool
    json_web_key_set_url: str
    authorization_url: str
    logout_url: str
    token_url: str
    user_info_url: str
    audience: str
    use_scope_permissions: bool
    user_pool_id: str
