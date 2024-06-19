from scgp_cip.common.enum import CIPOrderItemStatus

YMD_FORMAT = "%Y-%m-%d"
DMY_FORMAT = "%d/%m/%Y"
YMD_HMS_FORMAT = "%Y-%m-%d %H:%M:%S"
BOM_ITEM_CATEGORY_GROUP = "LUMF"
PRODUCTION_STATUS_PRODUCED = "ผลิต"
PRODUCTION_STATUS_NOT_PRODUCED = "ไม่ผลิต"
PMT_API_LAST_UPDATED_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
STATUS_ACTIVE = "Active"
BOM_FLAG_TRUE_VALUE = "X"
MANUAL_PRICE_FLAG_TRUE_VALUE = "X"
OTC_ACCOUNT_GROUPS = ["DOTT"]
DEFAULT_OTC_SOLD_TO_CODE = "0009999001"
PP_SOLD_TO_ACCOUNT_GROUPS = ["DREP", "Z001"]
CIP_SOLD_TO_ACCOUNT_GROUPS = ["DREP", "ZP01"]
SAP_RESPONSE_TRUE_VALUE = "X"
DEFAULT_ITEM_NO = "000000"
ORDER_PARTNER_AG = "AG"
DISABLE_SPLIT_ITEM_SATUS = [
    CIPOrderItemStatus.COMPLETE_DELIVERY.value,
    CIPOrderItemStatus.CANCEL.value,
]
ENABLE_SPLIT_ITEM_SATUS = [
    CIPOrderItemStatus.ITEM_CREATED.value,
    CIPOrderItemStatus.PARTIAL_DELIVERY.value,
]
REASON_REJECT = "93"
ITEM_NOTE_WHEN_NOT_PRODUCED = "SSS"

MAPPING_ITEM_ADDITIONAL_FIELDS = {
    "internal_comments_to_warehouse": "Z001",
    "external_comments_to_customer": "Z002",
    "remark": "Z004",
    "sale_text1": "0001",
    "sale_text2": "0001",
    "sale_text3": "0001",
    "sale_text4": "0001",
    "item_note": "0002",
    "pr_item_text": "Z021",
    "lot_no": "ZG23",
    "production_memo": "0006",
}

MAPPING_HEADER_ADDITIONAL_FIELDS = {
    "additional_txt_from_header": "0001",
    "additional_txt_header_note1": "0002",
    "internal_comments_to_logistic": "Z002",
    "internal_comments_to_warehouse": "Z001",
    "external_comments_to_customer": "Z067",
    "additional_txt_cash": "Z041",
    "cash": "Z041",
    "product_information": "ZK08",
    "web_username": "ZK01",
    "source_of_app": "Z095",
}

MAPPING_HEADER_ADDITIONAL_FIELDS_EXCEL_UPLOAD = {
    "additional_txt_header_note1": "0002",
    "internal_comments_to_logistic": "Z002",
    "internal_comments_to_warehouse": "Z001",
}
MAPPING_ITEM_ADDITIONAL_FIELDS_EXCEL_UPLOAD = {"item_note": "0002"}
HEADER_DOMESTIC = "Create Order From e-Ordering: Domestic"
EXCEL_HEADER_DOMESTIC = "Create Order From Excel UPLOAD: Domestic"
SCHEDULE_LINE = "0001"
HEADER_ORDER_KEY = "000000"
SAP_SCHEDULE_LINE_KEY = "0001"
SAP_ITEM_NOTE_CIP_NOT_PRODUCED_PREFIX = "SSS"
SHIP_SEARCH_ACCOUNT_GRP = ["ZP01", "ZP02", "ZP04"]
WARNING_CREDIT_STATUSES = {"B", "Z"}
CIP = "CIP"
FORCE_FLAG_VALUES = ["X", "x"]
