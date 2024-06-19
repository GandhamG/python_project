import enum

import graphene
from openpyxl.styles import Alignment

from scg_checkout import error_codes as checkout_error_codes
from utils.enums import IPlanInquiryMethodCode

ContractCheckoutErrorCode = graphene.Enum.from_enum(
    checkout_error_codes.ContractCheckoutErrorCode
)

ORDER_INFORMATION_REASON_REQUEST_DATE = "order_information.reason_for_change_request_date"

status_completed = "ผลิตครบถ้วน"

PP_BU = ["PP"]
CIP_BU = ["CIP"]


class ScgOrderStatus(graphene.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    FAILED_CONFIRM = "failed_confirm"
    RECEIVED_ORDER = "Received Order"
    CREDIT_CASH_ISSUE = "Credit/Cash Issue"
    PARTIAL_COMMITTED_ORDER = "Partial Committed Order"
    READY_FOR_DELIVERY = "Ready For Delivery"
    PARTIAL_DELIVERY = "Partial Delivery"
    COMPLETED_DELIVERY = "Completed Delivery"
    CANCELED = "Cancelled (93)"
    COMPLETED_ORDER = "Completed Order"
    PRE_DRAFT = "pre-draft"

    STATUS_RANK = [
        CONFIRMED,
        FAILED_CONFIRM,
        RECEIVED_ORDER,
        CREDIT_CASH_ISSUE,
        PARTIAL_COMMITTED_ORDER,
        READY_FOR_DELIVERY,
        PARTIAL_DELIVERY,
        COMPLETED_DELIVERY,
        COMPLETED_ORDER,
    ]


class ProductionStatus(graphene.Enum):
    UNALLOCATED = "Unallocated"
    ALLOCATED = "Allocated"
    CONFIRMED = "Confirm"
    CLOSE_RUN = "Closed Run"
    TRIMMED = "Trimmed"
    IN_PRODUCTION = "In Production"
    COMPLETED = "Completed"

    STATUS_RANK = [
        UNALLOCATED,
        ALLOCATED,
        CONFIRMED,
        CLOSE_RUN,
        TRIMMED,
        IN_PRODUCTION,
        COMPLETED,
    ]


class ContractOrder(graphene.Enum):
    ORDER_INFORMATION = "order_information"
    ORDER_ORGANIZATION_DATA = "order_organization_data"
    LINES = "lines"
    STATUS = "status"


class OrderInformation(graphene.Enum):
    CUSTOMER_ID = "customer_id"
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


class OrderLines(graphene.Enum):
    CHECKOUT_LINE_ID = "checkout_line_id"
    QUANTITY = "quantity"
    REQUEST_DATE = "request_date"
    PLANT = "plant"
    SHIP_TO = "ship_to"
    INTERNAL_COMMENTS_TO_WAREHOUSE = "internal_comments_to_warehouse"
    PRODUCT_INFORMATION = "product_information"
    VARIANT_ID = "variant_id"
    REQUIRED_FIELDS = [QUANTITY, REQUEST_DATE]


class AlternativeMaterialInputFields(graphene.Enum):
    FIELDS = {
        "sale_organization_id": "sale_organization_id",
        "sold_to_id": "sold_to_id",
        "material_own_id": "material_own_id",
        "lines": "lines",
    }


class AlternativeMaterial(graphene.Enum):
    MAX_UPLOAD_KB = 10 * 1024 * 1024  # Max 10MB
    SHEET_COLUMN_SIZE = 7
    DIA_LENGTH = 3
    SOLD_TO_CODE_LENGTH = 10
    SALE_ORG_LENGTH = 4


class AlternativeMaterialTypes(graphene.Enum):
    MATERIAL = "M"
    GRADE_GRAM = "G"


class ScgpClassMarkData(graphene.Enum):
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"


class Es21SapData(graphene.Enum):
    URL = "https://mulesoft-dev.scg-wedo.tech/exp_eordering/api/v1/salesOrder/sales/contract/changeSaleOrder"
    USERNAME = "scg_mulesoft_dev"
    PASSWORD = "scgxmulesoft2022"
    CLIENTID = "aaa"
    CLIENTSECRET = "aaa"


class ScgDomesticOrderType(graphene.Enum):
    ZOR = "ZOR"
    ZFC1 = "ZFC1"
    ZFC2 = "ZFC2"
    ZBV = "ZBV"


class ScgDomesticOrderStatusSAP(graphene.Enum):
    COMPLETE = "Complete"
    BEING_PROCESS = "Being Process"


class IPlanUseInventory(graphene.Enum):
    TRUE = True
    FALSE = False


class IPlanUseConsignmentInventory(graphene.Enum):
    TRUE = True
    FALSE = False


class IPlanUseProjectedInventory(graphene.Enum):
    TRUE = True
    FALSE = False


class IPlanUseProduction(graphene.Enum):
    TRUE = True
    FALSE = False


class IPlanOrderSplitLogic(graphene.Enum):
    SPLIT_MULTIPLE_DATE = "SPLIT MULTIPLE DATE"
    NO_SPLIT = "NO SPLIT"


class IPlanSingleSource(graphene.Enum):
    TRUE = True
    FALSE = False


class IPLanResponseStatus(graphene.Enum):
    FAILURE = "Failure"
    SUCCESS = "Success"
    PARTIAL_SUCCESS = "Partial Success"
    UNPLANNED = "Unplanned"
    TENTATIVE = "Tentative"


class IPLanConfirmStatus(graphene.Enum):
    COMMIT = "COMMIT"
    ROLLBACK = "ROLLBACK"


class ScgpDomesticOrderTax(graphene.Enum):
    TAX = 0.07


class OrderLineStatus(graphene.Enum):
    ENABLE = "Enable"
    CANCEL = "Cancel"
    DELETE = "Delete"


class RealtimePartnerType(graphene.Enum):
    SHIP_TO = "WE"
    BILL_TO = "RE"
    SOLD_TO = "AG"
    SALE_EMPLOYEE = "VE"
    PAYER = 'RG'


class IPlanTypeOfDelivery(graphene.Enum):
    EX_MILL = "E"
    ARRIVAL = "A"


class ScgOrderStatusSAP(graphene.Enum):
    COMPLETE = "Complete"
    BEING_PROCESS = "Being Process"


class MaterialVariantType(graphene.Enum):
    MATERIAL = ["81", "82"]
    GRADE_GRAM = "84"


class AltMaterialType(graphene.Enum):
    MATERIAL = ["81", "82"]
    GRADE_GRAM = ["84"]


class IPlanUpdateItemTime(graphene.Enum):
    BEFORE_PRODUCTION = "Before production"
    DURING_PRODUCTION = "During production"
    AFTER_PRODUCTION = "After production"


class IPlanUpdateOrderStatus(graphene.Enum):
    FAIL = "Fail"
    SUCCESS = "Success"


class ScgOrderlineAtpCtpStatus(graphene.Enum):
    ACCEPT = "accept"
    ROLLBACK = "rollback"


class IPlanOrderStatus(graphene.Enum):
    RECEIVED_ORDER = "Received Order"
    PARTIAL_COMMITTED_ORDER = "Partial Committed Order"
    READY_FOR_DELIVERY = "Ready For Delivery"
    PARTIAL_DELIVERY = "Partial Delivery"
    COMPLETED_DELIVERY = "Completed Delivery"
    CANCEL = "Cancelled (93)"
    COMPLETE_ORDER = "Complete Order"
    COMPLETED_PRODUCTION = "Completed Production"
    FULL_COMMITTED_ORDER = "Full Committed Order"

    IPLAN_ORDER_STATUS_TH = {
        RECEIVED_ORDER: "รับออเดอร์",
        PARTIAL_COMMITTED_ORDER: "มีสินค้าบางส่วน",
        READY_FOR_DELIVERY: "พร้อมส่ง",
        PARTIAL_DELIVERY: "จัดส่งบางส่วน",
        COMPLETED_DELIVERY: "จัดส่งสำเร็จ",
        CANCEL: "ยกเลิกออเดอร์",
        COMPLETE_ORDER: "ออเดอร์สมบูรณ์์",
        COMPLETED_PRODUCTION: status_completed,
        FULL_COMMITTED_ORDER: status_completed,
    }

    IPLAN_ORDER_RANK = [
        RECEIVED_ORDER,
        PARTIAL_COMMITTED_ORDER,
        COMPLETED_PRODUCTION,
        READY_FOR_DELIVERY,
        PARTIAL_DELIVERY,
        COMPLETED_DELIVERY,
        CANCEL,
        COMPLETE_ORDER
    ]


class IPlanOrderItemStatus(graphene.Enum):
    ITEM_CREATED = "Item Created"
    PLANNING_UNALLOCATED = "Planning (Unallocated)"
    PLANNING_ALLOCATED_NON_CONFIRM = "Planning (Allocated Non confirm)"
    PLANNING_CONFIRM = "Planning (Confirm)"
    PLANNING_CLOSE_LOOP = "Planning (Close Loop)"
    PLANNING_ALLOCATED_X_TRIM = "Planning (Allocated/X-Trim)"
    PLANNING_OUTSOURCING = "Planning (Outsourcing)"
    PRODUCING = "Producing"
    FULL_COMMITTED_ORDER = "Full Committed Order"
    COMPLETED_PRODUCTION = "Completed Production"
    PARTIAL_DELIVERY = "Partial Delivery"
    COMPLETE_DELIVERY = "Completed Delivery"
    CANCEL = "Cancelled (93)"
    FAILED = "failed"

    IPLAN_ORDER_LINES_STATUS_TH = {
        ITEM_CREATED: "สร้างรายการ",
        PLANNING_UNALLOCATED: "เตรียมเข้าผลิต",
        PLANNING_ALLOCATED_NON_CONFIRM: "กำลังวางแผนผลิต",
        PLANNING_CONFIRM: "ยินยันแผนผลิต",
        PLANNING_CLOSE_LOOP: "ปิด Run ผลิต",
        PLANNING_ALLOCATED_X_TRIM: "Trim การผลิต",
        PLANNING_OUTSOURCING: "กำลังหาสินค้า",
        PRODUCING: "กำลังผลิต",
        FULL_COMMITTED_ORDER: "มีสินค้าครบ",
        COMPLETED_PRODUCTION: status_completed,
        PARTIAL_DELIVERY: "จัดส่งบางส่วน",
        COMPLETE_DELIVERY: "ออเดอร์สมบูรณ์",
        CANCEL: "ยกเลิก"
    }

    MAPPING_ORDER_STATUS = {
        ITEM_CREATED: IPlanOrderStatus.RECEIVED_ORDER.value,
        PLANNING_UNALLOCATED: IPlanOrderStatus.PARTIAL_COMMITTED_ORDER.value,
        PLANNING_ALLOCATED_NON_CONFIRM: IPlanOrderStatus.PARTIAL_COMMITTED_ORDER.value,
        PLANNING_CONFIRM: IPlanOrderStatus.PARTIAL_COMMITTED_ORDER.value,
        PLANNING_CLOSE_LOOP: IPlanOrderStatus.PARTIAL_COMMITTED_ORDER.value,
        PLANNING_ALLOCATED_X_TRIM: IPlanOrderStatus.PARTIAL_COMMITTED_ORDER.value,
        PLANNING_OUTSOURCING: IPlanOrderStatus.PARTIAL_COMMITTED_ORDER.value,
        PRODUCING: IPlanOrderStatus.PARTIAL_COMMITTED_ORDER.value,
        FULL_COMMITTED_ORDER: IPlanOrderStatus.READY_FOR_DELIVERY.value,
        # SEO-4158: if Item status is "Completed Production" then Order status should be "Full Committed Order"
        COMPLETED_PRODUCTION: IPlanOrderStatus.FULL_COMMITTED_ORDER.value,
        PARTIAL_DELIVERY: IPlanOrderStatus.PARTIAL_DELIVERY.value,
        COMPLETE_DELIVERY: IPlanOrderStatus.COMPLETED_DELIVERY.value,
        CANCEL: IPlanOrderStatus.CANCEL.value
    }

    IPLAN_ORDER_LINE_RANK = [
        ITEM_CREATED,
        PLANNING_UNALLOCATED,
        PLANNING_ALLOCATED_NON_CONFIRM,
        PLANNING_CONFIRM,
        PLANNING_CLOSE_LOOP,
        PLANNING_ALLOCATED_X_TRIM,
        PLANNING_OUTSOURCING,
        PRODUCING,
        FULL_COMMITTED_ORDER,
        COMPLETED_PRODUCTION,
        PARTIAL_DELIVERY,
        COMPLETE_DELIVERY,
        CANCEL,
    ]


class DistributionChannelType(graphene.Enum):
    DOMESTIC = "domestic"
    EXPORT = "export"


class ContractOrderType(graphene.Enum):
    CREATE = "create"
    CHANGE = "change"


class SapOrderConfirmationStatus(graphene.Enum):
    READY_TO_SHIP = "พร้อมส่ง"
    QUEUE_FOR_PRODUCTION = "รอผลิต"
    CANCEL = "ยกเลิก"
    ALL = "All"

    SAP_ORDER_CONFIRMATION_STATUS_LIST = [
        READY_TO_SHIP,
        QUEUE_FOR_PRODUCTION,
        CANCEL
    ]


class SapOrderConfirmationStatusParam:
    ALL = "All"
    CONFIRM = "Confirm"
    NON_CONFIRM = "Non confirm"
    REJECT = "Reject"

    MAPPING_TO_TEXT = {
        CONFIRM: SapOrderConfirmationStatus.READY_TO_SHIP.value,
        NON_CONFIRM: SapOrderConfirmationStatus.QUEUE_FOR_PRODUCTION.value,
        REJECT: SapOrderConfirmationStatus.CANCEL.value
    }


class AtpCtpStatus(graphene.Enum):
    ATP = "ATP"
    ATP_FUTURE = "ATP Future"
    ATP_ON_HAND = "ATP OnHand"
    CTP = "CTP"


class PaymentTerm(graphene.Enum):
    DEFAULT = "NT00"
    AP00 = "AP00"


class DocType(graphene.Enum):
    ZBV = "ZBV"
    ZOR = "ZOR"


class TextIdSection(graphene.Enum):
    HEADER = "Header"
    ITEM = "Item"


class MaterialType(graphene.Enum):
    MATERIAL_WITHOUT_VARIANT = ["81", "82", "83"]
    MATERIAL_OS_PLANT = ["754F", "7531", "7533"]


class IPlanReATPRequiredCode(graphene.Enum):
    TRUE = True
    FALSE = False


class SalesOrgCode(graphene.Enum):
    SKIC = "0750"
    THAI = "7540"


class SapUpdateFlag(graphene.Enum):
    UPDATE = "U"
    INSERT = "I"
    DELETE = "D"


class DeliveryStatus(graphene.Enum):
    CANCEL = "A"
    PARTIAL_DELIVERY = "B"
    COMPLETED_DELIVERY = "C"


class LanguageCode(graphene.Enum):
    EN = "EN"
    TH = "TH"


class AlternatedMaterialLogChangeError(str, enum.Enum):
    NO_MATERIAL_CONTRACT = "No Material in ref. contract"
    NOT_FOUND_SAME_PRODUCT_GROUP = "Alternated materials found in different product group"
    NOT_FOUND_MATERIAL_DETERMINATION = "Not found material determination"
    NOT_ENOUGH_QTY_IN_CONTRACT = "Not enough Remaining Qty in ref. contract"
    NO_STOCK_ALT_MAT = "No Stock Alternated Material"


class AlternatedMaterialProductGroupMatch(graphene.Enum):
    NA = "NA"
    MATCHED = "MATCHED"
    NOT_MATCHED = "NOT_MATCHED"


class ReasonForChangeRequestDateEnum(graphene.Enum):
    C3 = "C3"
    C4 = "C4"
    X = "X"


class ReasonForChangeRequestDateDescriptionEnum(graphene.Enum):
    C3 = "C3-Logistics"
    C4 = "C4-Customer"
    X = ""


class WeightUnitEnum(graphene.Enum):
    TON = "TON"
    KG = "KG"


class CancelItem(graphene.Enum):
    CANCEL_93 = "Cancel 93"
    DELETE = "Delete"


class OrderEdit(graphene.Enum):
    # Format as {field_name_in_database: field_name_in_input}
    PARTNER = {
        "ship_to": "ship_to",
        "bill_to": "bill_to",
        "incoterms_1_id": "incoterms1",
        "customer_group_1_id": "customer_group_1",
        "customer_group_2_id": "customer_group_2",
        "customer_group_3_id": "customer_group_3",
        "customer_group_4_id": "customer_group_4",
        "po_date": "po_date",
        "po_no": "po_no",

    }
    ADDITIONAL_DATA = {
        "internal_comments_to_warehouse": "internal_comments_to_warehouse",
        "internal_comments_to_logistic": "internal_comments_to_logistic",
        "external_comments_to_customer": "external_comments_to_customer",
        "production_information": "production_information",
    }
    FIELDS = {
        "sold_to_code": "fixed_data.sold_to_code",
        "ship_to_code": "fixed_data.ship_to_code",
        "bill_to_code": "fixed_data.bill_to_code",
        "contract__code": "fixed_data.contract_no",
        "ship_to": "partner.ship_to",
        "bill_to": "partner.bill_to",
        "incoterms_1_id": "partner.incoterms1",
        "customer_group_1_id": "partner.customer_group_1",
        "customer_group_2_id": "partner.customer_group_2",
        "customer_group_3_id": "partner.customer_group_3",
        "customer_group_4_id": "partner.customer_group_4",
        "po_date": "partner.po_date",
        "po_no": "partner.po_no",
        "internal_comments_to_warehouse": "additional_data.internal_comments_to_warehouse",
        "internal_comments_to_logistic": "additional_data.internal_comments_to_logistic",
        "external_comments_to_customer": "additional_data.external_comments_to_customer",
        "production_information": "additional_data.production_information",
        "reason_for_change_request_date": ORDER_INFORMATION_REASON_REQUEST_DATE,
    }
    FIELDS_CHANGE = {
        "po_date": "partner.po_date",
        "ship_to": "partner.ship_to",
        "bill_to": "partner.bill_to",
        "incoterms_1_id": "partner.incoterms1",
        "customer_group_1_id": "partner.customer_group_1",
        "customer_group_2_id": "partner.customer_group_2",
        "customer_group_3_id": "partner.customer_group_3",
        "customer_group_4_id": "partner.customer_group_4",
        "po_no": "partner.po_no",
        "internal_comments_to_warehouse": "additional_data.internal_comments_to_warehouse",
        "internal_comments_to_logistic": "additional_data.internal_comments_to_logistic",
        "external_comments_to_customer": "additional_data.external_comments_to_customer",
        "production_information": "additional_data.production_information",
    }


class ItemDetailsEdit(graphene.Enum):
    # Format as {field_name_in_database: field_name_in_input}
    ORDER_INFORMATION = {
        "material_variant.code": "material_code",
        "request_date": "request_date",
        "request_date_change_reason": "reason_for_change_request_date",
        "quantity": "quantity",
        "unit": "unit",
        "plant": "plant",
        "shipping_point": "shipping_point",
        "item_category": "item_category",
        "route": "route",
        "po_no": "po_no",
        "delivery_tol_unlimited": "delivery_tolerance.unlimited",
        "delivery_tol_under": "delivery_tolerance.under",
        "delivery_tol_over": "delivery_tolerance.over"
    }

    IPLAN_DETAILS = {
        "inquiry_method": "input_parameter",
    }

    ADDITIONAL_DATA = {
        "ship_to_party": "ship_to_party",
        "internal_comments_to_warehouse": "internal_comments_to_warehouse",
        "external_comments_to_customer": "external_comments_to_customer",
        "remark": "remark"
    }

    FIELDS = {
        "material_variant.code": "order_information.material_code",
        "request_date": "order_information.request_date",
        "request_date_change_reason": ORDER_INFORMATION_REASON_REQUEST_DATE,
        "quantity": "order_information.quantity",
        "plant": "order_information.plant",
        "shipping_point": "order_information.shipping_point",
        "route": "order_information.route",
        "item_category": "order_information.item_category",
        "po_no": "order_information.po_no",
        "delivery_tol_unlimited": "order_information.delivery_tolerance.unlimited",
        "delivery_tol_under": "order_information.delivery_tolerance.under",
        "delivery_tol_over": "order_information.delivery_tolerance.over",
        "inquiry_method": "iplan_details.input_parameter",
        "consignment_location": "iplan_details.consignment_location",
        "ship_to": "additional_data.ship_to_party",
        "internal_comments_to_warehouse": "additional_data.internal_comments_to_warehouse",
        "external_comments_to_customer": "additional_data.external_comments_to_customer",
        "shipping_mark": "additional_data.shipping_mark"
    }
    UPDATE_ITEMS = {
        "material_code": "order_information.material_code",
        "request_date": "order_information.request_date",
        "reason_for_change_request_date": ORDER_INFORMATION_REASON_REQUEST_DATE,
        "quantity": "order_information.quantity",
        "unit": "order_information.unit",
        "plant": "order_information.plant",
        "shipping_point": "order_information.shipping_point",
        "route": "order_information.route",
        "po_no": "order_information.po_no",
        "unlimited": "order_information.delivery_tolerance.unlimited",
        "under": "order_information.delivery_tolerance.under",
        "over": "order_information.delivery_tolerance.over",
        "delivery_tolerance.input_parameter": "iplan_details.input_parameter"
    }

    NEW_ITEMS = {
        "material_code": "order_information.material_code",
        "request_date": "order_information.request_date",
        "reason_for_change_request_date": ORDER_INFORMATION_REASON_REQUEST_DATE,
        "quantity": "order_information.quantity",
        "unit": "order_information.unit",
        "plant": "order_information.plant",
        "shipping_point": "order_information.shipping_point",
        "route": "order_information.route",
        "item_category": "order_information.item_category",
        "po_no": "order_information.po_no",
        "unlimited": "order_information.delivery_tolerance.unlimited",
        "under": "order_information.delivery_tolerance.under",
        "over": "order_information.delivery_tolerance.over",
        "delivery_tolerance.input_parameter": "iplan_details.input_parameter"
    }


class InquiryMethodParameter(graphene.Enum):
    DOMESTIC = {
        "inquiry_method": IPlanInquiryMethodCode.JITCP.value,
        "use_inventory": IPlanUseInventory.TRUE.value,
        "use_consignment_inventory": IPlanUseConsignmentInventory.TRUE.value,
        "use_projected_inventory": IPlanUseProjectedInventory.TRUE.value,
        "use_production": IPlanUseProduction.TRUE.value,
        "order_split_logic": IPlanOrderSplitLogic.SPLIT_MULTIPLE_DATE.value,
        "single_source": IPlanSingleSource.FALSE.value,
        "re_atp_required": IPlanReATPRequiredCode.TRUE.value,
    }

    EXPORT = {
        "inquiry_method": IPlanInquiryMethodCode.JITCP.value,
        "use_inventory": IPlanUseInventory.FALSE.value,
        "use_consignment_inventory": IPlanUseConsignmentInventory.FALSE.value,
        "use_projected_inventory": IPlanUseProjectedInventory.FALSE.value,
        "use_production": IPlanUseProduction.TRUE.value,
        "order_split_logic": IPlanOrderSplitLogic.NO_SPLIT.value,
        "single_source": IPlanSingleSource.FALSE.value,
        "re_atp_required": IPlanReATPRequiredCode.FALSE.value,
    }

    ASAP = {
        "inquiry_method": IPlanInquiryMethodCode.ASAP.value,
        "use_inventory": IPlanUseInventory.TRUE.value,
        "use_consignment_inventory": IPlanUseConsignmentInventory.TRUE.value,
        "use_projected_inventory": IPlanUseProjectedInventory.TRUE.value,
        "use_production": IPlanUseProduction.TRUE.value,
        "order_split_logic": IPlanOrderSplitLogic.SPLIT_MULTIPLE_DATE.value,
        "single_source": IPlanSingleSource.FALSE.value,
        "re_atp_required": IPlanReATPRequiredCode.TRUE.value,
    }


class Es21Params(graphene.Enum):
    ORDER_HEADER_LN = {
        "po_no": "poNo",
        "po_date": "purchaseDate",
        "incoterms1": "incoterms1",
        "customer_group_1": "customerGroup1",
        "customer_group_2": "customerGroup2",
        "customer_group_3": "customerGroup3",
        "customer_group_4": "customerGroup4"
    }
    ORDER_PARTNER = {
        "ship_to": "WE",
        "bill_to": "RE"
    }
    ORDER_ITEMS = {
        "material_code": "material",
        "quantity": "targetQty",
        "unit": "salesUnit",
        "plant": "plant",
        "shipping_point": "shippingPoint",
        "route": "route",
        "po_no": "purchaseNoC",
        "item_category": "itemCategory",
        "over": "overdlvtol",
        "unlimited": "unlimitTol",
        "under": "unddlvTol",
    }
    ORDER_ITEMS_INX = {
        "material_code": "material",
        "quantity": "targetQty",
        "unit": "salesUnit",
        "plant": "plant",
        "shipping_point": "shippingPoint",
        "route": "route",
        "po_no": "custPoNo",
        "item_category": "itemCategory",
        "over": "overdlvtol",
        "unlimited": "unlimitTol",
        "under": "unddlvTol",
    }
    ORDER_ITEM_SPLIT = {
        "material_code": "material",
        "request_date": "material",
        "quantity": "targetQty"
    }
    ORDER_SCHEDULE = {
        "request_date": "reqDate",
        "quantity": "reqQty",
    }
    ORDER_SCHEDULE_INX = {
        "request_date": "requestDate",
        "quantity": "requestQuantity",
    }
    ORDER_TEXT = {
        "internal_comments_to_warehouse": "Z001",
        "internal_comments_to_logistic": "Z002",
        "external_comments_to_customer": "Z067",
        "production_information": "ZK08"
    }
    NEW_ITEM = {
        "quantity": "targetQty",
        "unit": "salesUnit",
        "plant": "plant",
        "shipping_point": "shippingPoint",
        "route": "route",
        "po_no": "purchaseNoC",
        "item_category": "itemCategory",
        "header_code": "poNo from i_plan_request",
        "request_date": "poDate"
    }


class DeliveryUnlimited(graphene.Enum):
    X = True
    Y = False


class UnitEnum(graphene.Enum):
    ROL = "ROL"


class InquiryOrderConfirmationStatus(graphene.Enum):
    ALL = "All"
    CONFIRM = "Confirm"
    NON_CONFIRM = "Non confirm"
    REJECT = "Reject"


status_text_1 = "เดินทางมาขึ้นสินค้า"
status_text_3 = "รอขึ้นสินค้า"
status_text_4 = "เดินทางไปลูกค้า"
status_text_5 = "ระหว่างลงสินค้า"
status_text_6 = "เดินทางกลับจากลูกค้า"
LMSStatusText = {
    "1": status_text_1,
    "2": status_text_1,
    "2.1": status_text_1,
    "2.2": status_text_1,
    "2.3": status_text_1,
    "2.4": status_text_1,
    "2a": status_text_1,
    "2b": status_text_1,
    "2c": status_text_1,
    "3": status_text_3,
    "4": status_text_4,
    "4.1": status_text_4,
    "4.2": status_text_4,
    "5": status_text_5,
    "6": status_text_6,
    "7": status_text_6,
    "7.1": status_text_6,
    "8": status_text_6,
    "8.1": status_text_6,
    "8.2": status_text_6,
    "8a": status_text_6,
    "8b": status_text_6,
    "9": status_text_6,
    "a1": status_text_1,
}

LMSStatusIdMapping = {
    "1": "2",
    "2": "2",
    "2.1": "2",
    "2.2": "2",
    "2.3": "2",
    "2.4": "2",
    "2a": "2",
    "2b": "2",
    "2c": "2",
    "3": "3",
    "4": "4",
    "4.1": "4",
    "4.2": "4",
    "5": "5",
    "6": "6",
    "7": "6",
    "7.1": "6",
    "8": "6",
    "8.1": "6",
    "8.2": "6",
    "8a": "6",
    "8b": "6",
    "9": "6",
    "a1": "2",
}


class POStatusEnum(graphene.Enum):
    N = "PO not approve"
    P = "PO approve"


class PendingOrderFieldHeaderColumn:
    def __init__(self):
        self._field = [
            {
                "index": 0,
                "en": "confirmDate",
                "th": "วันที่ประมาณ\nการส่งมอบ",
                "type": "date"
            },
            {
                "index": 1,
                "en": "orderDate",
                "th": "วันที่สั่งซื้อ\n(Create Date)",
                "type": "date"
            },
            {
                "index": 2,
                "en": "poNo",
                "th": "เลขที่ใบสั่งซื้อ PO\n(PO No.)",
                "type": "str"
            },
            {
                "index": 3,
                "en": "soNo",
                "th": "เลขที่ใบสั่งซื้อ SO\n(SO No.)",
                "type": "str"
            },
            {
                "index": 4,
                "en": "itemNo",
                "th": "ลำดับที่\n(Item No.)",
                "type": "int"
            },
            {
                "index": 5,
                "en": "materialCode",
                "th": "รายการสินค้า\n(Material Code)",
                "type": "str"
            },
            {
                "index": 6,
                "en": "materialDescription",
                "th": "รายละเอียดสินค้า\n(Material Description)",
                "type": "str"
            },
            {
                "index": 7,
                "en": "orderQty",
                "th": "จำนวนสั่งซื้อ\n(Order Qty)",
                "type": "float"
            },
            {
                "index": 8,
                "en": "pendingQty",
                "th": "จำนวนค้างส่ง\n(Pending Qty)",
                "type": "float"
            },
            {
                "index": 9,
                "en": "atpQty",
                "th": "พร้อมส่ง\n(ATP Qty)",
                "type": "float"
            },
            {
                "index": 10,
                "en": "ctpQty",
                "th": "รอผลิต\n(CTP Qty)",
                "type": "float"
            },
            {
                "index": 11,
                "en": "deliveryQty",
                "th": "ส่งแล้ว\n(Delivery Qty)",
                "type": "float"
            },
            {
                "index": 12,
                "en": "saleUnit",
                "th": "หน่วย\n(Unit)",
                "type": "str"
            },
            {
                "index": 13,
                "en": "shipTo",
                "th": "สถานที่ส่ง\n(Sold to)",
                "type": "str"
            }
        ]

    def find(self, key, value):
        if key == 'ALL':
            return self._field
        elif key == 'index' or key == 'en' or key == 'th':
            for item in self._field:
                if item[key] == value:
                    return item


class CustomerMaterialMapping(graphene.Enum):
    MAX_UPLOAD_KB = 10 * 1024 * 1024  # Max 10MB
    SHEET_COLUMN_SIZE = 5
    SOLD_TO_CODE_LENGTH = 10
    SALE_ORG_LENGTH = 4


class CustomerMaterialUploadError(graphene.Enum):
    FILE_TOO_LARGE = "ไฟล์มีขนาดเกิน 10 MB, กรุณาลองใหม่"
    INCORRECT_FILE_FORMAT = "รองรับไฟล์นามสกุล .xlsx เท่านั้น, กรุณาลองใหม่"


class CustomerMaterialHeaderColumn:
    def __init__(self):
        self._field = [
            {
                "index": 0,
                "field": "sold_to_code",
                "title": "Sold to code",
                "type": "string",
                "width": 10
            },
            {
                "index": 1,
                "field": "sales_organization_code",
                "title": "Sale Org.",
                "type": "string",
                "width": 4
            },
            {
                "index": 2,
                "field": "distribution_channel_code",
                "title": "Distribution Channel",
                "type": "string",
                "width": 2
            },
            {
                "index": 3,
                "field": "sold_to_material_code",
                "title": "Customer Material Code",
                "type": "string",
                "width": 35
            },
            {
                "index": 4,
                "field": "material_code",
                "title": "SAP Material Code",
                "type": "string",
                "width": 18
            },

        ]

    def find(self, key, value):
        if key == 'ALL':
            return self._field
        elif key == 'index' or key == 'field':
            for item in self._field:
                if item[key] == value:
                    return item

    def property_list(self, key):
        return [col[key] for col in self._field]


class CustomerMaterialSoldToSearchSuggestionFilters(graphene.Enum):
    ACCOUNT_GROUPS = ["Z001", "ZP01", "DREP"]
    DISTRIBUTION_CHANNEL = ["10", "20"]


ALIGNMENT_STYLE = Alignment(wrap_text=True, horizontal='left', vertical='top')
ALIGNMENT_VERTICAL_TOP = Alignment(vertical='top')


class ExcelUploadHeaderColumn:
    def __init__(self):
        self._field = [
            {"index": 0, "field": "sale_organization", "title": "Sale Organization", "type": "string", "width": 4,
             "required": True},
            {"index": 1, "field": "po_number", "title": "PO Number", "type": "string", "width": 35, "required": False},
            {"index": 2, "field": "sold_to", "title": "Sold-to", "type": "string", "width": 10, "required": True},
            {"index": 3, "field": "ship_to", "title": "Ship-to", "type": "string", "width": 10, "required": True},
            {"index": 4, "field": "bill_to", "title": "Bill-to", "type": "string", "width": 10, "required": False},
            {"index": 5, "field": "payer", "title": "Payer", "type": "string", "width": 10, "required": False},
            {"index": 6, "field": "request_date_header", "title": "Request Date Header", "type": "date", "width": 10,
             "required": True},
            {"index": 7, "field": "header_note1", "title": "Header Note 1", "type": "string", "width": 132},
            {"index": 8, "field": "internal_comment_to_warehouse", "title": "Internal comment to warehouse",
             "type": "string", "width": 132},
            {"index": 9, "field": "internal_comment_to_logistic", "title": "Internal comment to logistic",
             "type": "string", "width": 132},
            {"index": 10, "field": "material_code", "title": "Material Code/ Customer Material", "type": "string",
             "width": 35},
            {"index": 11, "field": "material_description", "title": "Material Description", "type": "string",
             "width": 40},
            {"index": 12, "field": "request_quantity", "title": "Request Quantity", "type": "decimal", "width": 17,
             "required": True},
            {"index": 13, "field": "request_date", "title": "Request Date", "type": "date", "width": 10,
             "required": True},
            {"index": 14, "field": "plant", "title": "Plant", "type": "string", "width": 4},
            {"index": 15, "field": "batch", "title": "Batch", "type": "string", "width": 10},
            {"index": 16, "field": "contract_no", "title": "Contract No.", "type": "string", "width": 10},
            {"index": 17, "field": "line_unit", "title": "Line unit", "type": "string", "width": 3},
            {"index": 18, "field": "width", "title": "Width", "type": "decimal", "width": 17},
            {"index": 19, "field": "length", "title": "Length", "type": "decimal", "width": 17},
            {"index": 20, "field": "dimension1", "title": "Dimension 1", "type": "decimal", "width": 17},
            {"index": 21, "field": "dimension2", "title": "Dimension 2", "type": "decimal", "width": 17},
            {"index": 22, "field": "dimension3", "title": "Dimension 3", "type": "decimal", "width": 17},
            {"index": 23, "field": "dimension4", "title": "Dimension 4", "type": "decimal", "width": 17},
            {"index": 24, "field": "dimension5", "title": "Dimension 5", "type": "decimal", "width": 17},
            {"index": 25, "field": "dimension6", "title": "Dimension 6", "type": "decimal", "width": 17},
            {"index": 26, "field": "production_memo", "title": "Production memo", "type": "string", "width": 132},
            {"index": 27, "field": "lot_no", "title": "Lot no.", "type": "string", "width": 35},
            {"index": 28, "field": "item_note", "title": "Item Note", "type": "string", "width": 132},
            {"index": 29, "field": "force_request_date", "title": "Force Request Date", "type": "string", "width": 1},
            {"index": 30, "field": "item_ship_to", "title": "Item Ship-to", "type": "string", "width": 10},

        ]

    def find(self, key, value):
        if key == 'ALL':
            return self._field
        elif key == 'index' or key == 'field':
            for item in self._field:
                if item[key] == value:
                    return item

    def property_list(self, key):
        return [col[key] for col in self._field]


class ExcelUploadMapping(graphene.Enum):
    MAX_UPLOAD_KB = 30 * 1024 * 1024  # Max 30MB
    SHEET_COLUMN_SIZE = 31
    SOLD_TO_CODE_LENGTH = 10
    SALE_ORG_LENGTH = 4


class EmailProductGroupConfig(graphene.Enum):
    UNDEFINED = "0000"
    ALL = "All"


class EmailSaleOrgConfig(graphene.Enum):
    UNDEFINED = "0000"
    ALL = "All"
