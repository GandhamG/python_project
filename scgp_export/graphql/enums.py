from enum import Enum
import graphene
from scgp_export import error_codes as scgp_export_error_codes

ScgpExportErrorCode = graphene.Enum.from_enum(
    scgp_export_error_codes.ScgpExportErrorCode
)


class ScgExportOrderType(graphene.Enum):
    ZOR = "ZOR"
    ZFC1 = "ZFC1"
    ZFC2 = "ZFC2"
    CREATE = "create"
    CHANGE = "change"


class ScgpExportOrderStatus(graphene.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    RECEIVED_ORDER = "Received Order"
    CREDIT_CASH_ISSUE = "Credit/Cash Issue"
    PARTIAL_COMMITTED_ORDER = "Partial Committed Order"
    READY_FOR_DELIVERY = "Ready For Delivery"
    PARTIAL_DELIVERY = "Partial Delivery"
    COMPLETED_DELIVERY = "Completed Delivery"
    CANCELLED = "Cancelled (93)"
    COMPLETED_ORDER = "Completed Order"
    PRE_DRAFT = "pre-draft"
    FULL_COMMITTED_ORDER = "Full Committed Order"


class ExportOrder(graphene.Enum):
    AGENCY = "agency"
    STATUS = "status"


class Agency(graphene.Enum):
    ORDER_TYPE = "order_type"
    SALES_ORGANIZATION_ID = "sales_organization_id"
    DISTRIBUTION_CHANNEL_ID = "distribution_channel_id"
    DIVISION_ID = "division_id"
    SALES_OFFICE_ID = "sales_office_id"
    SALES_GROUP_ID = "sales_group_id"
    REQUIRED_FIELDS = [
        ORDER_TYPE,
        SALES_ORGANIZATION_ID,
        DISTRIBUTION_CHANNEL_ID,
        DIVISION_ID,
        SALES_OFFICE_ID,
        SALES_GROUP_ID,
    ]


class ScgpExportOrder(graphene.Enum):
    TAX = 0.07
    COMMISSION = 0.1


class ScgExportRejectReason(graphene.Enum):
    YES = "Yes"
    NO = "No"


class ScgExportOrderLineAction(graphene.Enum):
    UPDATE = "Update"
    DELETE = "Delete"


class ScgpExportOrderStatusSAP(graphene.Enum):
    COMPLETE = "Complete"
    BEING_PROCESS = "Being Process"


class ScgpExportOrderLineWeightUnit(graphene.Enum):
    TON = "Ton"
    KG = "Kg."


class IPlanEndPoint(graphene.Enum):
    I_PLAN_PLUGIN_ID = "scg.i_plan_api"
    I_PLAN_REQUEST = "sales/available-to-promise/plan"
    I_PLAN_CONFIRM = "sales/available-to-promise/confirm"
    I_PLAN_SPLIT = "sales/contracts/order-updates"
    I_PLAN_UPDATE_ORDER = "sales/orders/updates"
    METHOD_POST = "POST"


class SapEnpoint(graphene.Enum):
    SAP_PLUGIN_ID = "scg.sap_client_api"
    METHOD_POST = "POST"
    METHOD_GET = "GET"
    ES_08 = "master-data/partners/search"
    ES_29 = "master-data/routes"
    ES_10 = "master-data/customers/1/credits"
    ES_13 = "contracts/search"
    ES_14 = "contracts"
    ES_15 = "sales/materials/search"
    ES_16 = "sales/orders"
    ES_17 = "sales/contracts/orders"
    ES_18 = "sales/orders"
    ES_25 = "sales/orders/search"
    ES_26 = "sales/orders/0410979783/status"
    ES_27 = "sales/quantities/date"
    ES_21 = "sales/contracts/orders/status"
    ES_41 = "sales/orders/prices"
    LMS_REPORT = "delivery-tracking"
    LMS_REPORT_GPS = "delivery-tracking/gps"


class OtsEndpoint(graphene.Enum):
    METHOD_POST = "POST"
    METHOD_GET = "GET"
    OTS = "order-tracking"


class ATPCTPActionType(graphene.Enum):
    COMMIT = "commit"
    ROLLBACK = "rollback"


class ItemCat(graphene.Enum):
    ZKSO = "ZKSO"
    ZKC0 = "ZKC0"
    ZMTO = "ZMTO"
    ZNTT = "ZNTT"
    ZTNN = "ZTNN"
    ZTN1 = "ZTN1"


class MaterialGroup(graphene.Enum):
    PK00 = "PK00"


class TextID(graphene.Enum):
    HEADER_ICTW = "Z001"
    HEADER_ICTL = "Z002"
    HEADER_ECTC = "Z067"
    HEADER_PI = "ZK08"
    HEADER_PAYIN = "Z012"
    HEADER_REMARK = "Z016"
    ITEM_ICTW = "Z001"
    ITEM_ICTL = ""
    ITEM_ECTC = "Z002"
    ITEM_PI = ""
    ITEM_SHIPPING_MARK = "Z004"
    ITEM_REMARK = "Z020"
    HEADER_ETD = "Z038"
    HEADER_ETA = "Z066"
    HEADER_PORT_OF_DISCHARGE = "Z013"
    HEADER_PORT_OF_LOADING = "Z014"
    HEADER_NO_OF_CONTAINERS = "Z022"
    HEADER_DLC_EXPIRY_DATE = "Z223"
    HEADER_DLC_LATEST_DELIVERY_DATE = "Z224"
    HEADER_DLC_NO = "Z222"
    HEADER_UOM = "Z019"
    HEADER_GW_UOM = "ZK35"
    SYSTEM_SOURCE = "Z095"
    WEB_USERNAME = "ZK01"
    MATERIAL_ITEM_ROLL_DIAMETER = "Z008"
    MATERIAL_ITEM_ROLL_CORE_DIAMETER = "Z009"
    MATERIAL_ITEM_NO_OF_ROLLS = "Z003"
    MATERIAL_ITEM_REAM_ROLL_PER_PALLET = "Z011"
    MATERIAL_ITEM_PALLET_SIZE = "Z010"
    MATERIAL_ITEM_PALLET_NO = "Z005"
    MATERIAL_ITEM_NO_OF_PACKAGE = "Z006"
    MATERIAL_ITEM_PACKING_LIST = "Z017"
    ITEM_REMARK_PO_UPLOAD = "0006"


text_id_list_eo = [
    TextID.WEB_USERNAME.value,
    TextID.SYSTEM_SOURCE.value,
    TextID.HEADER_ICTW.value,
    TextID.HEADER_PORT_OF_DISCHARGE.value,
    TextID.HEADER_NO_OF_CONTAINERS.value,
    TextID.HEADER_UOM.value,
    TextID.HEADER_GW_UOM.value,
    TextID.HEADER_ETD.value,
    TextID.HEADER_ETA.value,
    TextID.HEADER_DLC_EXPIRY_DATE.value,
    TextID.HEADER_DLC_NO.value,
    TextID.HEADER_DLC_LATEST_DELIVERY_DATE.value,
    TextID.HEADER_PAYIN.value,
    TextID.HEADER_REMARK.value,
    TextID.HEADER_PI.value,
    TextID.ITEM_SHIPPING_MARK.value,
    TextID.ITEM_ICTW.value,
    TextID.MATERIAL_ITEM_PALLET_NO.value,
    TextID.MATERIAL_ITEM_NO_OF_ROLLS.value,
    TextID.MATERIAL_ITEM_PALLET_SIZE.value,
    TextID.MATERIAL_ITEM_NO_OF_PACKAGE.value,
    TextID.ITEM_REMARK_PO_UPLOAD.value,
    TextID.MATERIAL_ITEM_PACKING_LIST.value,
    TextID.MATERIAL_ITEM_ROLL_DIAMETER.value,
    TextID.MATERIAL_ITEM_ROLL_CORE_DIAMETER.value,
    TextID.MATERIAL_ITEM_REAM_ROLL_PER_PALLET.value
]


class ChangeExportRejectReason(graphene.Enum):
    CANCEL_93 = 'Cancel 93'
    DELETE = 'Delete'


class IPlanResponseStatus(Enum):
    FAILURE = "FAILURE"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL SUCCESS"
    UNPLANNED = "UNPLANNED"
    TENTATIVE = "TENTATIVE"


class Es21Map(graphene.Enum):
    ORDER_HEADER_IN = {}
    ORDER_PARTNER = {}
    ORDER_ITEMS = {}
    ORDER_ITEMS_INX = {}
    ORDER_ITEM_SPLIT = {}
    ORDER_SCHEDULE = {
        "reqDate": "request_date",
        "reqQty": "quantity"
    }
    ORDER_SCHEDULE_INX = {}
    ORDER_TEXT = {
        "Z004": "shipping_mark",
    }
    NEW_ITEM = {  # es21 -> input
        "targetQty": "quantity",
        "salesUnit": "sale_unit",
        "plant": "plant",  # response iplan
        "shippingPoint": "shipping_point",
        "route": "route",
        "itemCategory": "item_cat_eo",
        "poNo": "headerCode",
        "overdlvtol": "delivery_tol_over",
        "unlimitTol": "delivery_tol_unlimited",
        "unddlvTol": "delivery_tol_under",
        "poDate": "po_date"
    }
