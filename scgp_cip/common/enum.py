from enum import Enum

import graphene


class CipOrderErrorCode(str, Enum):
    ALREADY_EXISTS = "already_exists"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    REQUIRED = "required"
    UNIQUE = "unique"


class CipOrderInput(graphene.Enum):
    ORDER_INFORMATION = "order_information"
    ORDER_ORGANIZATION_DATA = "order_organization_data"
    LINES = "lines"
    STATUS = "status"


class OrderInformation(graphene.Enum):
    CUSTOMER_ID = "customer_id"
    PAYMENT_TERM = "payment_term"
    TAX_CLASSIFICATION = "tax_classification"
    PO_DATE = "po_date"
    PO_NUMBER = "po_number"
    REQUEST_DATE = "request_date"
    ORDER_TYPE = "order_type"
    SHIP_TO = "ship_to"
    BILL_TO = "bill_to"
    INTERNAL_COMMENTS_TO_WAREHOUSE = "internal_comments_to_warehouse"
    INTERNAL_COMMENTS_TO_LOGISTIC = "internal_comments_to_logistic"
    EXTERNAL_COMMENTS_TO_CUSTOMER = "external_comments_to_customer"
    PRODUCT_INFORMATION = "product_information"
    UNLOADING_POINT = "unloading_point"
    REQUIRED_FIELDS = [
        PO_NUMBER,
        REQUEST_DATE,
        SHIP_TO,
        BILL_TO,
    ]


class OrderOrganizationData(graphene.Enum):
    SALE_ORGANIZATION_ID = "sale_organization_id"
    DISTRIBUTION_CHANNEL_ID = "distribution_channel_id"
    DIVISION_ID = "division_id"
    SALE_OFFICE_ID = "sale_office_id"
    SALE_GROUP_ID = "sale_group_id"
    REQUIRED_FIELDS = [
        SALE_ORGANIZATION_ID,
        DISTRIBUTION_CHANNEL_ID,
        DIVISION_ID,
        SALE_OFFICE_ID,
        SALE_GROUP_ID,
    ]


class OrderInformationSubmit(graphene.Enum):
    CUSTOMER_ID = "customer_id"
    PAYMENT_TERM = "payment_term"
    TAX_CLASS = "tax_class"
    PO_DATE = "po_date"
    PO_NUMBER = "po_number"
    REQUEST_DATE = "request_date"
    ORDER_TYPE = "order_type"
    SHIP_TO = "ship_to"
    BILL_TO = "bill_to"
    INTERNAL_COMMENTS_TO_WAREHOUSE = "internal_comments_to_warehouse"
    INTERNAL_COMMENTS_TO_LOGISTIC = "internal_comments_to_logistic"
    EXTERNAL_COMMENTS_TO_CUSTOMER = "external_comments_to_customer"
    PRODUCT_INFORMATION = "product_information"
    UNLOADING_POINT = "unloading_point"
    REQUIRED_FIELDS = [
        REQUEST_DATE,
        TAX_CLASS,
        PAYMENT_TERM,
        ORDER_TYPE,
    ]


class OrderOrganizationDataSubmit(graphene.Enum):
    SALE_ORGANIZATION_ID = "sale_organization_code"
    DISTRIBUTION_CHANNEL_ID = "distribution_channel_code"
    DIVISION_ID = "division_code"
    SALE_OFFICE_ID = "sale_office_code"
    SALE_GROUP_ID = "sale_group_code"
    REQUIRED_FIELDS = [SALE_ORGANIZATION_ID, DISTRIBUTION_CHANNEL_ID, DIVISION_ID]


class OrderLines(graphene.Enum):
    QUANTITY = "quantity"
    REQUEST_DATE = "request_date"
    PLANT = "plant"
    SHIP_TO = "ship_to"
    INTERNAL_COMMENTS_TO_WAREHOUSE = "internal_comments_to_warehouse"
    PRODUCT_INFORMATION = "product_information"
    ITEM_NO = "item_no"
    REQUIRED_FIELDS = [QUANTITY, REQUEST_DATE]


class PmtEndpoint(graphene.Enum):
    PMT_MAT_SEARCH = "sales/products/catalog"


class MatSearchThirdPartySystem(graphene.Enum):
    PMT = "pmt"


class PriceCalculationThirdPartySystem(graphene.Enum):
    SAP_ES41 = "sap_es_41"


class MaterialTypes(graphene.Enum):
    SERVICE_MATERIAL = "85"
    OUTSOURCE_MATERIAL = "82"
    OWN_MATERIAL = "81"


class OrderSolutionEndpoint(graphene.Enum):
    CP = "sales/temp-orders"


class OrderSolutionThirdPartySystem(graphene.Enum):
    CP = "cp"


class CPRequestType(graphene.Enum):
    NEW = "New"
    CHANGED = "Changed"


class SearchMaterialBy(graphene.Enum):
    CUST_MAT_CODE = "cust_mat_code"
    MAT_CODE = "mat_code"


class ItemCat(graphene.Enum):
    ZKSO = "ZKSO"
    ZKC0 = "ZKC0"
    ZMTO = "ZMTO"
    ZNTT = "ZNTT"
    ZTNN = "ZTNN"
    ZTN1 = "ZTN1"
    ZPS1 = "ZPS1"
    ZPSH = "ZPSH"
    ZPSI = "ZPSI"
    ZPS2 = "ZPS2"
    ZPS0 = "ZPS0"


class OrderType(graphene.Enum):
    DOMESTIC = "domestic"
    CUSTOMER = "customer"
    EXPORT = "export"
    EO = "eo"
    PO = "po"


class ProductionFlag(graphene.Enum):
    PRODUCED = "ผลิต"
    NOT_PRODUCED = "ไม่ผลิต"


class BatchNoType(graphene.Enum):
    NOT_SPECIFY = "ไม่ระบุ"


class CIPOrderItemStatus(graphene.Enum):
    RECEIVED_ORDER = "Received Order"
    ITEM_CREATED = "Item Created"
    PARTIAL_DELIVERY = "Partial Delivery"
    COMPLETE_DELIVERY = "Completed Delivery"
    CANCEL = "Cancelled (93)"

    CIP_ORDER_LINES_STATUS_TH = {
        RECEIVED_ORDER: "รับออเดอร์",
        ITEM_CREATED: "สร้างรายการ",
        PARTIAL_DELIVERY: "จัดส่งบางส่วน",
        COMPLETE_DELIVERY: "ออเดอร์สมบูรณ์",
        CANCEL: "ยกเลิก",
    }


class CIPOrderPaymentType(graphene.Enum):
    CASH = "ZP20"
    CREDIT = "ZP30"


class ES26ItemStatus(graphene.Enum):
    CREATED = "A"
    PARTIAL_DELIVERY = "B"
    COMPLETED_OR_CANCELLED = "C"


class ThirdPartySystemApi(graphene.Enum):
    SAP_ES_18 = "ES_18"


class CpApiMessage(graphene.Enum):
    SUCCESS = "Success"


class SAP_FLAG(graphene.Enum):
    UPDATE = "U"
    INSERT = "I"
    DELETE = "D"


class CipCancelItemStatus(graphene.Enum):
    Cancel = "Cancel"
    Delete = "Delete"


class MappingLevel(graphene.Enum):
    ITEM_LEVEL = "item_level"
    HEADER_LEVEL = "header_level"


class Es26ConditionType(graphene.Enum):
    SERVICE_MAT_PRICE_IN_SAP = "ZPS1"
    SERVICE_MAT_NO_PRICE_IN_SAP = "ZPS2"
    OTHER_MAT_TYPE = "ZPP1"


class ScheduleLineCategory(graphene.Enum):
    CN = "CN"


class PPOrderTypes(graphene.Enum):
    ZOR = "ZOR - ชำระด้วย Credit"
    ZBV = "ZBV - ชำระด้วยเงินสด"


class CIPOrderTypes(graphene.Enum):
    ZP20 = "ZP20 - ชำระด้วยเงินสด"
    ZP30 = "ZP30 - ชำระด้วย Credit"
