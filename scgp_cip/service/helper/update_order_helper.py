import uuid

from scg_checkout.graphql.enums import OrderLineStatus


def prepare_params_for_cancel_delete_es18(so_no, order_lines_input, order_lines):

    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": so_no,
        "orderItemsIn": [],
        "orderItemsInx": [],
    }

    for order_line in order_lines_input:
        order_line_db = order_lines.get(order_line.get("item_no"))
        status = order_line["status"]
        mapping = {
            "itemNo": order_line_db.item_no,
            "material": order_line_db.material_code,
            "targetQty": order_line_db.quantity,
            "salesUnit": order_line_db.sales_unit,
        }

        if status == OrderLineStatus.CANCEL.value:
            mapping.update(
                {
                    "reasonReject": "93",
                }
            )
            params["orderItemsInx"].append(
                {
                    "itemNo": order_line_db.item_no,
                    "updateflag": "U",
                    "reasonReject": True,
                }
            )

        else:
            params["orderItemsInx"].append(
                {"itemNo": order_line_db.item_no, "updateflag": "D"}
            )
        params["orderItemsIn"].append(mapping)
    return params
