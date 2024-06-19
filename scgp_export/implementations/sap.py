from saleor.core.management.commands.update_permissions import ScgpUserGroup
from sap_migration.graphql.enums import OrderType


def get_web_user_name(order_type: OrderType, user):
    web_user_line = ""

    def _get_user_role():
        if not user.scgp_user:
            return ""
        role = "Domestic"
        group_name = (
            user.scgp_user.user_parent_group
            and user.scgp_user.user_parent_group.name
            or ""
        )
        if group_name == ScgpUserGroup.CUSTOMER:
            role = "Customer"
        elif group_name == ScgpUserGroup.CS_DOMESTIC:
            role = "Domestic"
        elif group_name == ScgpUserGroup.CS_EXPORT:
            role = "Export"
        return role

    role = _get_user_role()
    if order_type == OrderType.EO:
        web_user_line = "Create Order From EO UPLOAD\n" f"{user.id} eOrdering System"
    elif order_type == OrderType.PO:
        web_user_line = "".join(
            [
                "Create Order From PO UPLOAD: %s\n" % role,
                f"{user.id} {user.first_name} {user.last_name}",
            ]
        )
    elif order_type == OrderType.DOMESTIC:
        web_user_line = "".join(
            [
                "Create Order From e-Ordering: %s\n" % role,
                f"{user.id} {user.first_name} {user.last_name}",
            ]
        )
    elif order_type == OrderType.EXPORT:
        web_user_line = (
            "Create Order From e-Ordering: Export\n"
            f"{user.id} {user.first_name} {user.last_name}"
        )

    return web_user_line
