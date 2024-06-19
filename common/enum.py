from enum import Enum


class HTTP_METHOD(Enum):
    GET = "GET"
    POST = "POST"


class ChangeItemScenario(str, Enum):
    # https://scgdigitaloffice.atlassian.net/wiki/spaces/EO/pages/568459342/Change+detail+in+order+item+level
    SCENARIO_1 = "SCENARIO_1"
    SCENARIO_2 = "SCENARIO_2"
    SCENARIO_3 = "SCENARIO_3"


class EorderingItemStatusEN(Enum):
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


class EorderingItemStatusTH(Enum):
    ITEM_CREATED = "สร้างรายการ"
    PLANNING_UNALLOCATED = "เตรียมเข้าผลิต"
    PLANNING_ALLOCATED_NON_CONFIRM = "กำลังวางแผนผลิต"
    PLANNING_CONFIRM = "ยินยันแผนผลิต"
    PLANNING_CLOSE_LOOP = "ปิด Run ผลิต"
    PLANNING_ALLOCATED_X_TRIM = "Trim การผลิต"
    PLANNING_OUTSOURCING = "กำลังหาสินค้า"
    PRODUCING = "กำลังผลิต"
    FULL_COMMITTED_ORDER = "มีสินค้าครบ"
    COMPLETED_PRODUCTION = "ผลิตครบถ้วน"
    PARTIAL_DELIVERY = "จัดส่งบางส่วน"
    COMPLETE_DELIVERY = "ออเดอร์สมบูรณ์"
    CANCEL = "ยกเลิก"


class ChangeOrderAPIFlow(Enum):
    YT65156 = "YT65156"  # Follow the flow to call YT65156
    YT65217 = "YT65217"  # _______________________ YT65217
    NO_API_CALL = "NO_API_CALL"  # No Api needed to change order


class MulesoftServiceType(Enum):
    SAP = "sap"
    IPLAN = "iplan"
    CP = "cp"
    OTS = "ots"
    PMT = "pmt"


class MulesoftFeatureType(Enum):
    CREATE_ORDER = "CreateOrder"
    CHANGE_ORDER = "ChangeOrder"
    DELETE_ITEM = "DeleteItem"
    SPLIT_ITEM = "SplitItem"
    UNDO_ITEM = "UndoItem"
    DTR_DTP = "DTRDTP"
    ADD_ITEM = "AddItem"


class ProductGroupSpec(Enum):
    PLANT_BLANK_GROUP = ["K01", "K09"]
    PLANT_GROUP = ["K02", "K04", "K06"]
    WEIGHT_UNIT_BAG = ["K04"]
    WEIGHT_UNIT_REAM = ["K02"]
    WEIGHT_UNIT_TON = ["K01", "K09", "K06"]
    SALE_UNIT_BAG = ["K04"]
    SALE_UNIT_REAM = ["K02"]
    SALE_UNIT_ROL = ["K01", "K09"]
    SALE_UNIT_TON = ["K06"]
    PRODUCT_GROUP = PLANT_BLANK_GROUP + PLANT_GROUP
