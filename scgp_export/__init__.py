class ScgpExportOrderStatus:
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    RECEIVED_ORDER = "Received Order"
    CREDIT_CASH_ISSUE = "Credit/Cash Issue"
    PARTIAL_COMMITTED_ORDER = "Partial Committed Order"
    READY_FOR_DELIVERY = "Ready For Delivery"
    PARTIAL_DELIVERY = "Partial Delivery"
    COMPLETED_DELIVERY = "Completed Delivery"
    CANCELED = "Canceled"
    COMPLETED_ORDER = "Completed Order"


class ScgpExportOrderStatusSAP:
    COMPLETE = "Complete"
    BEING_PROCESS = "Being Process"
