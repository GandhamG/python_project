from sap_migration.models import Order


def get_sap_message(order: Order, message_obj: dict) -> dict:
    return {
        "id": message_obj.get("id", ""),
        "number": message_obj.get("number", ""),
        "message": message_obj.get("message", ""),
        "so_no": order.so_no if order else "",
    }
