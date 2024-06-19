from dataclasses import dataclass


@dataclass
class ScgSendEmailConfig:
    host: str
    port: str
    username: str
    password: str
    use_ssl: bool
    use_tls: bool
    sender_name: str
    sender_address: str
    reset_password_url: str
    reset_password_time_out: str
    reset_password_limit: str
    password_wrong_number: str
    time_lock_user: str
    require_attention_url: str
