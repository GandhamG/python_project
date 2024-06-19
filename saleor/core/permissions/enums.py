from enum import Enum
from typing import Iterable, List

from django.contrib.auth.models import Permission


class BasePermissionEnum(Enum):
    @property
    def codename(self):
        return self.value.split(".")[1]


class AccountPermissions(BasePermissionEnum):
    MANAGE_USERS = "account.manage_users"
    MANAGE_STAFF = "account.manage_staff"
    IMPERSONATE_USER = "account.impersonate_user"


class AppPermission(BasePermissionEnum):
    MANAGE_APPS = "app.manage_apps"


class ChannelPermissions(BasePermissionEnum):
    MANAGE_CHANNELS = "channel.manage_channels"


class DiscountPermissions(BasePermissionEnum):
    MANAGE_DISCOUNTS = "discount.manage_discounts"


class PluginsPermissions(BasePermissionEnum):
    MANAGE_PLUGINS = "plugins.manage_plugins"


class GiftcardPermissions(BasePermissionEnum):
    MANAGE_GIFT_CARD = "giftcard.manage_gift_card"


class MenuPermissions(BasePermissionEnum):
    MANAGE_MENUS = "menu.manage_menus"


class CheckoutPermissions(BasePermissionEnum):
    MANAGE_CHECKOUTS = "checkout.manage_checkouts"
    HANDLE_CHECKOUTS = "checkout.handle_checkouts"


class OrderPermissions(BasePermissionEnum):
    MANAGE_ORDERS = "order.manage_orders"


class PaymentPermissions(BasePermissionEnum):
    HANDLE_PAYMENTS = "payment.handle_payments"


class PagePermissions(BasePermissionEnum):
    MANAGE_PAGES = "page.manage_pages"


class PageTypePermissions(BasePermissionEnum):
    MANAGE_PAGE_TYPES_AND_ATTRIBUTES = "page.manage_page_types_and_attributes"


class ProductPermissions(BasePermissionEnum):
    MANAGE_PRODUCTS = "product.manage_products"


class ProductTypePermissions(BasePermissionEnum):
    MANAGE_PRODUCT_TYPES_AND_ATTRIBUTES = "product.manage_product_types_and_attributes"


class ShippingPermissions(BasePermissionEnum):
    MANAGE_SHIPPING = "shipping.manage_shipping"


class SitePermissions(BasePermissionEnum):
    MANAGE_SETTINGS = "site.manage_settings"
    MANAGE_TRANSLATIONS = "site.manage_translations"


class ScgpPermissions(BasePermissionEnum):
    # Shopping
    VIEW_ORDER_CUSTOMER = "scgp_user_management.scgp_view_order_customer"
    CREATE_ORDER_CUSTOMER = "scgp_user_management.scgp_create_order_customer"
    CHANGE_ORDER_CUSTOMER = "scgp_user_management.scgp_change_order_customer"
    VIEW_ORDER_DOMESTIC = "scgp_user_management.scgp_view_order_domestic"
    CREATE_ORDER_DOMESTIC = "scgp_user_management.scgp_create_order_domestic"
    CHANGE_ORDER_DOMESTIC = "scgp_user_management.scgp_change_order_domestic"
    VIEW_ORDER_EXPORT = "scgp_user_management.scgp_view_order_export"
    CREATE_ORDER_EXPORT = "scgp_user_management.scgp_create_order_export"
    CHANGE_ORDER_EXPORT = "scgp_user_management.scgp_change_order_export"
    CREATE_ORDER_DOMESTIC_PACKAGING = (
        "scgp_user_management.scgp_create_order_packaging_domestic"
    )
    # Dummy
    VIEW_DUMMY = "scgp_user_management.scgp_view_dummy"
    CREATE_DUMMY = "scgp_user_management.scgp_create_dummy"
    CHANGE_DUMMY = "scgp_user_management.scgp_change_dummy"
    APPROVE_DUMMY = "scgp_user_management.scgp_approve_dummy"
    # Maintain
    MAINTAIN_USER = "scgp_user_management.scgp_maintain_user"
    MAINTAIN_USER_GROUP = "scgp_user_management.scgp_maintain_user_group"
    MAINTAIN_ROLE = "scgp_user_management.scgp_maintain_role"
    MAINTAIN_ROLE_PERMISSION = "scgp_user_management.scgp_maintain_role_permission"
    MAINTAIN_ORGANIZATION = "scgp_user_management.scgp_maintain_organization"
    MAINTAIN_ALT_MATERIAL = "scgp_user_management.scgp_maintain_alt_material"
    MAINTAIN_PO_UPLOAD = "scgp_user_management.scgp_maintain_po_upload"
    MAINTAIN_EMAIL = "scgp_user_management.scgp_maintain_email"
    MAINTAIN_EMAIL_EO_UPLOAD = "scgp_user_management.scgp_maintain_email_eo_upload"
    MAINTAIN_CUSTOMER_MATERIAL = "scgp_user_management.scgp_maintain_customer_material"
    VIEW_PENDING_ORDER_TRACKING = (
        "scgp_user_management.scgp_view_pending_order_tracking"
    )
    VIEW_SALE_ORDER_TRACKING = "scgp_user_management.scgp_view_sale_order_tracking"
    VIEW_ORDER_CONFIRM_REPORT = "scgp_user_management.scgp_view_order_confirm"
    # Misc.
    ALL_UPLOAD_PO_CUSTOMER = "scgp_user_management.scgp_all_upload_po_customer"
    ALL_UPLOAD_PO_ADMIN = "scgp_user_management.scgp_all_upload_po_admin"
    ALL_CONTRACT = "scgp_user_management.scgp_all_contract"
    ALL_REPORT_CUSTOMER = "scgp_user_management.scgp_all_report_customer"
    ALL_REPORT_ADMIN = "scgp_user_management.scgp_all_report_admin"
    ALL_REPORT_DOMESTIC = "scgp_user_management.scgp_all_report_domestic"
    ALL_REPORT_EXPORT = "scgp_user_management.scgp_all_report_export"
    VIEW_STOCK = "scgp_user_management.scgp_view_stock"
    VIEW_DRAFT_ORDER = "scgp_user_management.scgp_view_draft_order"
    MAINTAIN_EXCEL_UPLOAD = "scgp_user_management.scgp_maintain_excel_upload"


PERMISSIONS_ENUMS = [
    AccountPermissions,
    AppPermission,
    ChannelPermissions,
    DiscountPermissions,
    PluginsPermissions,
    GiftcardPermissions,
    MenuPermissions,
    OrderPermissions,
    PagePermissions,
    PageTypePermissions,
    PaymentPermissions,
    ProductPermissions,
    ProductTypePermissions,
    ShippingPermissions,
    SitePermissions,
    CheckoutPermissions,
    ScgpPermissions,
]


def get_permissions_codename():
    permissions_values = [
        enum.codename
        for permission_enum in PERMISSIONS_ENUMS
        for enum in permission_enum
    ]
    return permissions_values


def get_permissions_enum_list():
    permissions_list = [
        (enum.name, enum.value)
        for permission_enum in PERMISSIONS_ENUMS
        for enum in permission_enum
    ]
    return permissions_list


def get_permissions_enum_dict():
    return {
        enum.name: enum
        for permission_enum in PERMISSIONS_ENUMS
        for enum in permission_enum
    }


def get_permissions_from_names(names: List[str]):
    """Convert list of permission names - ['MANAGE_ORDERS'] to Permission db objects."""
    permissions = get_permissions_enum_dict()
    return get_permissions([permissions[name].value for name in names])


def get_permission_names(permissions: Iterable["Permission"]):
    """Convert Permissions db objects to list of Permission enums."""
    permission_dict = get_permissions_enum_dict()
    names = set()
    for perm in permissions:
        for _, perm_enum in permission_dict.items():
            if perm.codename == perm_enum.codename:
                names.add(perm_enum.name)
    return names


def split_permission_codename(permissions):
    return [permission.split(".")[1] for permission in permissions]


def get_permissions(permissions=None):
    if permissions is None:
        codenames = get_permissions_codename()
    else:
        codenames = split_permission_codename(permissions)
    return get_permissions_from_codenames(codenames)


def get_permissions_from_codenames(permission_codenames: List[str]):
    return (
        Permission.objects.filter(codename__in=permission_codenames)
        .prefetch_related("content_type")
        .order_by("codename")
    )
