import enum

import graphene

from scgp_po_upload import error_codes as scgp_po_upload_error_codes

Scgp_PoUpload_ErrorCode = graphene.Enum.from_enum(
    scgp_po_upload_error_codes.ScgpPoUploadErrorCode
)


class POUploadFlag(str, enum.Enum):
    HEADER = "H"
    ITEM = "I"


class PoUploadType:
    EXCEL = "E"
    TXT = "T"
    CHOICES = [(EXCEL, "E"), (TXT, "T")]


class SaveToSapStatus:
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    BEING_PROCESS = "being_process"
    FAIL = "fail"
    UPLOAD_FILE = "upload file"
    IN_QUEUE = "in_queue"
    CALL_IPLAN_REQUEST = "call_iPlan_request"
    CALL_SAP = "call SAP"
    CALL_IPLAN_CONFIRM = "call_iPlan_confirm"

    CHOICES = [
        (IN_PROGRESS, "In Progress"),
        (SUCCESS, "Success"),
        (BEING_PROCESS, "Being Process"),
        (FAIL, "Fail"),
        (UPLOAD_FILE, "Upload file"),
        (IN_QUEUE, "in queue"),
        (CALL_IPLAN_REQUEST, "call iPlan request"),
        (CALL_SAP, "call sap"),
        (CALL_IPLAN_CONFIRM, "call iPlan confirm")
    ]


class PoSns(enum.Enum):
    SUBJECT = "Uploaded File"
    MESSAGE = "Uploaded File"


class SapType(enum.Enum):
    SUCCESS = "success"
    ERROR = "fail"


class SapUpdateType(enum.Enum):
    SUCCESS = "success"
    FAIL = "fail"


class IplanAction(enum.Enum):
    APPLY = "apply"
    REJECT = "reject"
    CONFIRM = "confirm"


class IPlanAcknowledge(enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class SAP21(enum.Enum):
    SUCCESS = "success"
    FAILED = "fail"


class SAP27(enum.Enum):
    SUCCESS = "success"
    FAILED = "fail"


class BeingProcessConstants:
    BEING_PROCESS_CODE = "042"
    BEING_PROCESS_CODE_ID = "V1"


class PoUploadMode:
    CUSTOMER = "A"
    CS_ADMIN = "B"


class ResponseCodeES17:
    BLACKLIST_CUSTOMER = {"code": "423", "message": "Blacklist Customer"}
    BEING_PROCESS = {"code": "042", "message": "Being Process"}


class MessageErrorItem:
    """
    ITEM_LEVEL_ERROR_MESSAGE only includes item error-message mapping of static SAP messages. Mapping of dynamic sap
    messages like "Material & does not exist in plant & " are handling in get_item_level_message function.
    """
    ITEM_LEVEL_ERROR_MESSAGE = {
        "E01": "สินค้านี้ไม่ได้ปรากฏอยู่ใน  Contract",
        "E02": "สินค้านี้ได้ถูกนำมาสร้างใบสั่งซื้อโดยอ้างอิงจาก Contract จนครบแล้ว",
        "E03": "ไม่พบรหัสสินค้า",
        "E04": "ไม่พบ Contract ดังกล่าวในระบบ",
        "E05": "สินค้านี้อยู่ในกลุ่มสินค้าประเภทอื่นๆ (Material Group)",
        "E06": "โปรดตรวจสอบ Text file",
        "E07": "จำนวนทับรอยไม่ถูกต้อง",
        "E08": "ไม่พบรหัสสถานที่ส่งสินค้าที่สัมพันธ์กับรหัสลูกค้าของท่าน",
        "E09": "วันที่ส่งสินค้าไม่อยู่ในช่วงที่กำหนด",
        "E10": "สินค้านี้มีจำนวนที่เหลืออยู่ใน Contract ไม่พอที่จะสร้างใบสั่งซื้อ",
        "E11": "ไม่สามารถแปลงหน่วยของสินค้าได้",
        "E12": "ลำดับที่สินค้าในใบสั่งซื้อและรหัสสินค้าไม่สอดคล้องกัน",
        "E13": "ไม่มีสินค้าที่สามารถสร้างใบสั่งซื้อได้",
        "E14": "ไม่พบใบสั่งซื้อดังกล่าวในระบบ",
        "E15": "ไม่พบสินค้าดังกล่าวในระบบ",
        "E16": "สินค้าดังกล่าวกำลังถูกเตรียมจัดส่ง ไม่สามารถแก้ไขได้",
        "E17": "เลขที่สินค้านี้ซ้ำกับสินค้าอื่นในใบสั่งซื้อของท่าน",
        "E18": "ไม่มีสินค้าที่สามารถเปลี่ยนแปลงได้ในใบสั่งซื้อ",
        "E19": "สินค้าบางรายการได้ถูกเตรียมจัดส่งแล้ว ไม่สามารถยกเลิกได้",
        "E20": "เลขที่ใบสั่งซื้อนี้มีอยู่แล้วใบระบบ ไม่สามารถสร้างซ้ำได้",
        "E21": "รหัสลูกค้าของท่าน ได้ถูกเตรียมในระบบเพื่อสร้างใบสั่งซื้อ",
        "E22": "Contract ดังกล่าวยังไม่ได้รับการอนุมัติ",
        "E23": "โปรดตรวจสอบใบสั่งซื้อ (Incompletion log)",
        "E24": "หน่วยสินค้าไม่ถูกต้อง",
        "E25": "สินค้าดังกล่าวได้ถูกเปลี่ยนสถานะแล้ว ไม่สามารถแก้ไขได้",
        "E26": "Contract ดังกล่าวได้หมดอายุแล้ว",
        "E27": "ขนาดสินค้าใหญ่เกินไป",
        "E28": "ขนาดสินค้าเล็กเกินไป",
        "E29": "หน่วยของสินค้า Sheet board ไม่ถูกต้อง",
        "E30": "ผลรวมของค่าทับรอยไม่ถูกต้อง",
        "E33": "สินค้านี้ไม่มีส่วนลด AND ",
        "E34": "Reference item has reason for rejection (93)",
        "E36": "รหัสสินค้าดังกล่าวไม่มีข้อมูลราคาในระบบ",
        "E37": "รหัสสินค้าดังกล่าวไม่พบใน BOM"
    }


class ContractErrorMessage:
    ERROR_CODE_MESSAGE = {"Contract end date was on": {"code": "ER02", "message": "Contract ดังกล่าวได้หมดอายุแล้ว"},
                          "The document has not yet been approved.": {"code": "ER03",
                                                                      "message": "Contract ดังกล่าวยังไม่ได้รับการอนุมัติ"},
                          "The document has already been completely copied or rejected.": {"code": "ER04",
                                                                                           "message": "สินค้านี้ได้ถูกนำมาสร้างใบสั่งซื้อโดยอ้างอิงจาก Contract จนครบแล้ว"},
                          "Data not found": {"code": "ER05", "message": "ไม่พบ Contract ดังกล่าวในระบบ"},
                          "Material Group is out of scope.": {"code": "ER06",
                                                              "message": "สินค้านี้อยู่ในกลุ่มสินค้าประเภทอื่นๆ (Material Group)"}
                          }
    TECHNICAL_ERROR = "ER99 - ไม่สามารถทำรายการได้ เนื่องจากระบบขัดข้อง โปรดติดต่อผู้ดูแลระบบ"


class UploadType(graphene.Enum):
    GROUP = "GROUP"
    NOT_GROUP = "NOT_GROUP"
