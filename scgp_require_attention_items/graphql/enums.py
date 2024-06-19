import graphene

from scg_checkout.graphql.enums import IPlanOrderItemStatus
from scgp_require_attention_items import error_codes as scgp_require_attention_items_error_codes

ScgpRequireAttentionItemsErrorCode = graphene.Enum.from_enum(
    scgp_require_attention_items_error_codes.ScgpRequireAttentionItemsErrorCode
)


class ScgpRequireAttentionType(graphene.Enum):
    R1 = "Confirm date diff"
    R2 = "Confirm QTY diff"
    R3 = "Stock diff"
    R4 = "Conflict ETD"


class ScgpRequireAttentionTypeData(graphene.Enum):
    ALL = "All"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"
    R5 = "R5"
class SourceOfAppData(graphene.Enum):
    ALL="All"
    EO_UPLOAD="Create Order From EO UPLOAD"
    PO_UPLOAD_CUSTOMER="Create Order From PO UPLOAD: Customer"
    PO_UPLOAD_DOMESTIC="Create Order From PO UPLOAD: Domestic"
    EXPORT_ORDER_SCREEN="Create Order From e-Ordering: Export"
    CUSTOMER_ORDER_SCREEN="Create Order From e-Ordering: Customer"
    DOMESTIC_ORDER_SCREEN="Create Order From e-Ordering: Domestic"
    EXCEL_UPLOAD_ON_SCREEN_DOMESTIC="Create Order From Excel UPLOAD: Domestic"
    EXCEL_UPLOAD_ON_SCREEN_CS="Create Order From Excel UPLOAD: Customer"
    EXCEL_UPLOAD_OCR="Create Order From OCR Excel UPLOAD: Domestic"

class ScgpRequireAttentionItemStatus(graphene.Enum):
    PLANNING_UNALLOCATED = IPlanOrderItemStatus.PLANNING_UNALLOCATED.value
    PLANNING_ALLOCATED_NON_CONFIRM = IPlanOrderItemStatus.PLANNING_ALLOCATED_NON_CONFIRM.value
    PLANNING_CONFIRM = IPlanOrderItemStatus.PLANNING_CONFIRM.value
    PLANNING_CLOSE_LOOP = IPlanOrderItemStatus.PLANNING_CLOSE_LOOP.value
    PLANNING_ALLOCATED_X_TRIM = IPlanOrderItemStatus.PLANNING_ALLOCATED_X_TRIM.value
    PLANNING_OUTSOURCING = IPlanOrderItemStatus.PLANNING_OUTSOURCING.value
    PRODUCING = IPlanOrderItemStatus.PRODUCING.value
    FULL_COMMITTED_ORDER = IPlanOrderItemStatus.FULL_COMMITTED_ORDER.value
    COMPLETED_PRODUCTION = IPlanOrderItemStatus.COMPLETED_PRODUCTION.value
    PARTIAL_DELIVERY = IPlanOrderItemStatus.PARTIAL_DELIVERY.value
    COMPLETE_DELIVERY = IPlanOrderItemStatus.COMPLETE_DELIVERY.value
    CANCEL = IPlanOrderItemStatus.CANCEL.value
    ITEM_CREATED = IPlanOrderItemStatus.ITEM_CREATED.value

class ScgpRequireAttentionTypeOfDelivery(graphene.Enum):
    ARRIVAL = "Arrival"
    EX_MILL = "Ex-mill"


class ScgpRequireAttentionSplitOrderItemPartialDelivery(graphene.Enum):
    YES = "Yes"
    NO = "No"


class ScgpRequireAttentionConsignment(graphene.Enum):
    FREE_STOCK_1000 = "1000 - Free Stock"
    FREE_STOCK_1001 = "1001 - Free Stock"
    FREE_STOCK_1002 = "1002 - Free Stock"


class MaterialPricingGroupEnum(graphene.Enum):
    STANDARD = "Standard"
    NON_STANDARD = "Non standard"


class DeliveryBlock09Enum(graphene.Enum):
    BLOCK = "Block"
    UNBLOCK = "Unblock"


class SaleOrderStatusEnum(graphene.Enum):
    ALL = ""
    PENDING = "G"
    COMPLETE = "I"


class Direction(graphene.Enum):
    ASC = "ASC"
    DESC = "DESC"


class IPlanEndpoint(graphene.Enum):
    METHOD_POST = "POST"
    METHOD_GET = "GET"
    DOMAIN = "scg.i_plan_api"
    REQUEST_URL = "sales/available-to-promise/plan"
    I_PLAN_UPDATE_ORDER = "sales/orders/updates"
    IPLAN_CONFIRM_URL = "sales/available-to-promise/confirm"
    I_PLAN_SPLIT = "sales/contracts/order-updates"
    I_PLAN_SPLIT_ORDER = "sales/contracts/order-splits"


class ReasonForReject(graphene.Enum):
    CANCEL_93 = 'Cancel 93'
    DELETE = 'Delete'


class ChangeOrderStatusEnum(graphene.Enum):
    ALL = ""
    COMPLETE = "C"
    OPEN = "O"


class ChangeOrderOrderStatus(graphene.Enum):
    ALL = ["Received Order", "Credit/Cash Issue", "Partial Committed Order", "Ready For Delivery",
           "Partial Delivery", "Completed Delivery", "Cancelled (93)", "Completed Order"]
    RECEIVED_ORDER = "Received Order"
    CREDIT_CASH_ISSUE = "Credit/Cash Issue"
    PARTIAL_COMMITTED_ORDER = "Partial Committed Order"
    READY_FOR_DELIVERY = "Ready For Delivery"
    PARTIAL_DELIVERY = "Partial Delivery"
    COMPLETED_DELIVERY = "Completed Delivery"
    CANCELLED = "Cancelled (93)"
    COMPLETED_ORDER = "Completed Order"


class MappingProductGroup:
    def __init__(self):
        self._groups = [
            {
                "code": "K01",
                "message": "Kraft",
            },
            {
                "code": "K09",
                "message": "Gypsum",
            },
        ]

    def find(self, key, value):
        for item in self._groups:
            if item[key] == value:
                return item
        return None
