import graphene

from scgp_customer import error_codes as scgp_customer_error_codes

ScgpCustomerErrorCode = graphene.Enum.from_enum(
    scgp_customer_error_codes.ScgpCustomerErrorCode
)


class ScgpCustomerOrderStatus(graphene.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PRE_DRAFT = "pre-draft"


class ScgpCustomerOrderTax(graphene.Enum):
    TAX = 0.07


class CustomerOrder(graphene.Enum):
    ORDER_INFORMATION = "order_information"
    LINES = "lines"


class CustomerOrderInformation(graphene.Enum):
    ORDER_DATE = "order_date"
    ORDER_NO = "order_no"
    REQUEST_DELIVERY_DATE = "request_delivery_date"
    SHIP_TO = "ship_to"
    BILL_TO = "bill_to"
    UNLOADING_POINT = "unloading_point"
    REMARK_FOR_INVOICE = "remark_for_invoice"
    REMARK_FOR_LOGISTIC = "remark_for_logistic"
    REQUIRED_FIELDS = [
        ORDER_DATE,
        ORDER_NO,
        REQUEST_DELIVERY_DATE,
        SHIP_TO,
        BILL_TO,
        UNLOADING_POINT,
    ]


class CustomerOrderLine(graphene.Enum):
    CONTRACT_PRODUCT_ID = "contract_product_id"
    VARIANT_ID = "variant_id"
    QUANTITY = "quantity"
    REQUIRED_FIELDS = [
        CONTRACT_PRODUCT_ID,
        # VARIANT_ID,
        QUANTITY,
    ]
