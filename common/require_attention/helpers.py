from typing import List

from sap_migration.models import OrderLines


def add_flag_attention(order_line: OrderLines, flags: List[str]) -> None:
    flags.sort()
    # If empty attention type, return flags from input
    attention_type = order_line.attention_type or ""
    if not attention_type:
        order_line.attention_type = ", ".join(flags)

    attention_type_arr = list(set(attention_type.split(",") + flags))
    attention_type_arr.sort()
    order_line.attention_type = ", ".join(attention_type_arr)


def remove_flag_attention(order_line: OrderLines, flags: List[str]) -> None:
    attention_type = order_line.attention_type
    # If empty attention type, do nothing
    if not attention_type:
        return

    attention_type_set = set(attention_type.split(", "))
    flags_set = set(flags)

    remaining_flags = list(attention_type_set - flags_set)
    remaining_flags.sort()

    order_line.attention_type = ", ".join(remaining_flags)
