from scgp_user_management.models import ScgpUser
from utils.enums import ParentGroupCode


def is_customer_user(user):
    scgp_user = ScgpUser.objects.select_related("user_parent_group").get(user=user)
    return ParentGroupCode.CUSTOMER.value == scgp_user.user_parent_group.code


def is_domestic_user(user):
    scgp_user = ScgpUser.objects.select_related("user_parent_group").get(user=user)
    return ParentGroupCode.CS_DOMESTIC.value == scgp_user.user_parent_group.code


def is_export_user(user):
    scgp_user = ScgpUser.objects.select_related("user_parent_group").get(user=user)
    return ParentGroupCode.CS_EXPORT.value == scgp_user.user_parent_group.code
