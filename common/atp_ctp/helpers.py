from .enums import AtpCtpStatus


def get_atp_ctp(i_plan_on_hand_stock, i_plan_operations) -> str:
    if not i_plan_operations:
        return AtpCtpStatus.ATP.value
    if not i_plan_on_hand_stock:
        return AtpCtpStatus.CTP.value
    return ""


def get_atp_ctp_detail(i_plan_on_hand_stock, i_plan_operations):
    atp_ctp_status = None
    if i_plan_on_hand_stock is True and not i_plan_operations:
        atp_ctp_status = AtpCtpStatus.ATP.value
    elif i_plan_on_hand_stock is False and not i_plan_operations:
        atp_ctp_status = AtpCtpStatus.ATP_FUTURE.value
    elif i_plan_on_hand_stock is False and i_plan_operations:
        atp_ctp_status = AtpCtpStatus.CTP.value
    return atp_ctp_status
