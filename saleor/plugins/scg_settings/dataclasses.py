from dataclasses import dataclass


@dataclass
class ScgSettings:
    enable_mulesoft_log: bool
    enable_upload_user: bool
    enable_target_qty_decimal_round_up: bool
    enable_alt_mat_outsource_feature: bool
