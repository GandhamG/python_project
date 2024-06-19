from typing import TypedDict

RETURN_CODE_LENGTH = 32


class IPlanResponseMessageType(TypedDict):
    item_no: str
    first_code: str
    second_code: str
    message: str


def get_iplan_message(response_line) -> IPlanResponseMessageType:
    code = response_line.get("returnCode", "")
    first_code = ""
    second_code = ""
    if len(code) == RETURN_CODE_LENGTH:
        first_code = code[18:24]
        second_code = code[24:32]
    item_no = response_line.get("lineNumber", "")
    message = response_line.get("returnCodeDescription", "")

    return {
        "item_no": item_no,
        "first_code": first_code,
        "second_code": second_code,
        "message": message,
    }


def get_yt65217_message(response_line) -> IPlanResponseMessageType:
    item_no = response_line.get("lineCode", "")
    message = response_line.get("returnCodeDescription", "")
    error_code = response_line.get("returnCode", "1")
    return {
        "item_no": item_no,
        "first_code": error_code,
        "second_code": "",
        "message": message,
    }
