import logging
from enum import Enum

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from saleor.account.models import AccountPermissions
from saleor.core.permissions.enums import ScgpPermissions
from scgp_user_management.models import (
    GroupMenuFunctions,
    MenuFunction,
    ParentGroup,
    ScgpGroup,
)


class ScgpUserGroup:
    ADMIN = "Admin"
    CS_DOMESTIC = "CS Domestic"
    CS_EXPORT = "CS Export"
    CUSTOMER = "Customer"
    MANAGER = "Manager"
    PRODUCTION_PLANNING = "Production Planning"
    SALES = "Sales"
    SECTION = "Section"
    SS_SERVICE_SOLUTION = "SS(Service Solution)"


class ScgpUserRole:
    INQUIRY_CUSTOMER = "Inquiry Customer"
    INQUIRY = "Inquiry"
    INQUIRY_DOMESTIC = "Inquiry Domestic"
    INQUIRY_EXPORT = "Inquiry Export"
    MAINTAIN = "Maintain"
    PO_UPLOAD = "PO Upload"
    PO_UPLOAD_CUSTOMER = "PO Upload Customer"
    SEARCH_DUMMY = "Search dummy"
    SHOPPING_CUSTOMER = "Shopping Customer"
    SHOPPING_DOMESTIC = "Shopping domestic"
    SHOPPING_EXPORT = "Shopping export"
    CS_MAINTAIN = "CS Maintain"
    CUSTOMER_MATERIAL = "Maintain Customer Master"
    SHOPPING_DOMESTIC_PACKAGING = "Shopping domestic - Packaging"
    INQUIRY_DOMESTIC_ORDER_TRACK = "Inquiry domestic - Order Tracking"
    EXCEL_UPLOAD = "Excel Upload"


class MenuFunctions(Enum):
    CREATE_ORDER_DOMESTIC = "Create Order (CS Domestic)"
    SEARCH_CHANGE_ORDER_DOMESTIC = "Search & Change Order (CS Domestic)"
    REQUIRED_ATTENTION = "Required Attention"
    CREATE_ORDER_PACKAGING = "Create Order Packaging"
    CREATE_ORDER_SHEET_BOARD = "Create Order Sheet board"
    CREATE_ORDER_EXPORT = "Create Order (CS Export)"
    SEARCH_CHANGE_ORDER_EXPORT = "Search & Change Order (CS Export)"
    CHANGE_MASS = "Change Mass "
    PO_UPLOAD = "PO Upload"
    EXCEL_UPLOAD = "Excel Upload "
    LIST_SALES_ORDER_REPORT = "List Of Sales Order Report"
    PENDING_ORDER_REPORT = "Pending Order Report"
    ORDER_CONFIRMATION_REPORT = "Order Confirmation Report"
    DELIVERY_REPORT_LMS = "Delivery Report (LMS)"
    SALES_REPORT_KOS = "Sales Report (KOS System)"
    STOCK_ONHAND_REPORT = "Stock onhand Report"
    IPLAN_REPORT = "iPlan Report"
    LIST_SALES_ORDER_REPORT_ORDER_TRACKING = (
        "List Of Sales Order Report Order Tracking "
    )
    PENDING_ORDER_REPORT_ORDER_TRACKING = "Pending Order Report Order Tracking "
    ALTERNATED_MATERIAL = "Alternated Material"
    USER_MANAGEMENT = "User Management "
    EMAIL_CONFIGURATION = "Email Configuration"
    CUSTOMER_MATERIAL = "Customer Material"
    CREATE_ORDER_SHEETBOARD = "Create Order Sheetboard"
    CREATE_ORDER_CUSTOMER = "Create Order Customer"
    SEARCH_ORDER_CUSTOMER = "Search Order Customer"
    CREATE_ORDER_CUSTOMER_SHEETBOARD = "Create Order Customer Sheetboard"
    SEARCH_ORDER = "ค้นหาใบสั่งซื้อ (Search Order)"
    PENDING_ORDER_REPORT_CUSTOMER = "รายการใบสั่งซื้อค้างส่ง (Pending Order Report)"
    EXTERNAL_LINK = "รายงานสรุปยอดซื้อ (External Link)"


GROUP_ROLE_CONFIG = {
    ScgpUserGroup.ADMIN: [
        ScgpUserRole.PO_UPLOAD,
        ScgpUserRole.SHOPPING_EXPORT,
        ScgpUserRole.SHOPPING_DOMESTIC,
        ScgpUserRole.INQUIRY_DOMESTIC,
        ScgpUserRole.INQUIRY_EXPORT,
        ScgpUserRole.MAINTAIN,
        ScgpUserRole.CUSTOMER_MATERIAL,
        ScgpUserRole.SHOPPING_DOMESTIC_PACKAGING,
        ScgpUserRole.INQUIRY_DOMESTIC_ORDER_TRACK,
        ScgpUserRole.EXCEL_UPLOAD,
    ],
    ScgpUserGroup.CS_DOMESTIC: [
        ScgpUserRole.PO_UPLOAD,
        ScgpUserRole.SHOPPING_DOMESTIC,
        ScgpUserRole.INQUIRY_DOMESTIC,
        # ScgpUserRole.SEARCH_DUMMY,  # Not used yet, need to confirm in the future
        ScgpUserRole.CS_MAINTAIN,
        ScgpUserRole.CUSTOMER_MATERIAL,
        ScgpUserRole.SHOPPING_DOMESTIC_PACKAGING,
        ScgpUserRole.INQUIRY_DOMESTIC_ORDER_TRACK,
        ScgpUserRole.EXCEL_UPLOAD,
    ],
    ScgpUserGroup.CS_EXPORT: [
        ScgpUserRole.SHOPPING_EXPORT,
        ScgpUserRole.INQUIRY_EXPORT,
    ],
    ScgpUserGroup.CUSTOMER: [
        ScgpUserRole.INQUIRY_CUSTOMER,
        ScgpUserRole.PO_UPLOAD_CUSTOMER,
        ScgpUserRole.SHOPPING_CUSTOMER,
    ],
    ScgpUserGroup.MANAGER: [
        ScgpUserRole.INQUIRY_DOMESTIC,
        ScgpUserRole.INQUIRY_EXPORT,
        ScgpUserRole.INQUIRY_DOMESTIC_ORDER_TRACK,
    ],
    ScgpUserGroup.PRODUCTION_PLANNING: [
        ScgpUserRole.INQUIRY_DOMESTIC,
        ScgpUserRole.INQUIRY_EXPORT,
        ScgpUserRole.INQUIRY_DOMESTIC_ORDER_TRACK,
    ],
    ScgpUserGroup.SALES: [
        ScgpUserRole.INQUIRY_DOMESTIC,
        ScgpUserRole.INQUIRY_EXPORT,
        ScgpUserRole.SHOPPING_DOMESTIC,
        ScgpUserRole.SHOPPING_EXPORT,
        ScgpUserRole.INQUIRY_DOMESTIC_ORDER_TRACK,
    ],
    ScgpUserGroup.SECTION: [
        ScgpUserRole.INQUIRY_DOMESTIC,
        ScgpUserRole.INQUIRY_EXPORT,
        ScgpUserRole.SHOPPING_DOMESTIC,
        ScgpUserRole.SHOPPING_EXPORT,
        ScgpUserRole.INQUIRY_DOMESTIC_ORDER_TRACK,
    ],
    ScgpUserGroup.SS_SERVICE_SOLUTION: [
        ScgpUserRole.INQUIRY_DOMESTIC,
        ScgpUserRole.INQUIRY_EXPORT,
        ScgpUserRole.INQUIRY_DOMESTIC_ORDER_TRACK,
    ],
}
ROLE_PERMISSION_CONFIG = {
    ScgpUserRole.INQUIRY: [
        ScgpPermissions.ALL_REPORT_ADMIN.codename,
        ScgpPermissions.VIEW_STOCK.codename,
    ],
    ScgpUserRole.INQUIRY_DOMESTIC: [
        ScgpPermissions.ALL_REPORT_DOMESTIC.codename,
        ScgpPermissions.VIEW_STOCK.codename,
        ScgpPermissions.VIEW_ORDER_DOMESTIC.codename,
        ScgpPermissions.ALL_REPORT_ADMIN.codename,
    ],
    ScgpUserRole.INQUIRY_EXPORT: [
        ScgpPermissions.ALL_REPORT_EXPORT.codename,
        ScgpPermissions.VIEW_STOCK.codename,
        ScgpPermissions.VIEW_ORDER_EXPORT.codename,
    ],
    ScgpUserRole.INQUIRY_CUSTOMER: [ScgpPermissions.ALL_REPORT_CUSTOMER.codename],
    ScgpUserRole.MAINTAIN: [
        AccountPermissions.MANAGE_STAFF.codename,
        ScgpPermissions.MAINTAIN_USER.codename,
        ScgpPermissions.MAINTAIN_USER_GROUP.codename,
        ScgpPermissions.MAINTAIN_ROLE.codename,
        ScgpPermissions.MAINTAIN_ROLE_PERMISSION.codename,
        ScgpPermissions.MAINTAIN_ORGANIZATION.codename,
        ScgpPermissions.MAINTAIN_ALT_MATERIAL.codename,
        ScgpPermissions.MAINTAIN_PO_UPLOAD.codename,
        ScgpPermissions.MAINTAIN_EMAIL.codename,
        ScgpPermissions.MAINTAIN_EMAIL_EO_UPLOAD.codename,
    ],
    ScgpUserRole.PO_UPLOAD: [
        ScgpPermissions.ALL_UPLOAD_PO_ADMIN.codename,
    ],
    ScgpUserRole.PO_UPLOAD_CUSTOMER: [
        ScgpPermissions.ALL_UPLOAD_PO_CUSTOMER.codename,
    ],
    ScgpUserRole.SEARCH_DUMMY: [ScgpPermissions.VIEW_DUMMY.codename],
    ScgpUserRole.SHOPPING_CUSTOMER: [
        ScgpPermissions.VIEW_ORDER_CUSTOMER.codename,
        ScgpPermissions.CREATE_ORDER_CUSTOMER.codename,
        ScgpPermissions.CHANGE_ORDER_CUSTOMER.codename,
    ],
    ScgpUserRole.SHOPPING_DOMESTIC: [
        ScgpPermissions.VIEW_ORDER_DOMESTIC.codename,
        ScgpPermissions.CREATE_ORDER_DOMESTIC.codename,
        ScgpPermissions.CHANGE_ORDER_DOMESTIC.codename,
        ScgpPermissions.VIEW_DRAFT_ORDER.codename,
    ],
    ScgpUserRole.SHOPPING_EXPORT: [
        ScgpPermissions.VIEW_ORDER_EXPORT.codename,
        ScgpPermissions.CREATE_ORDER_EXPORT.codename,
        ScgpPermissions.CHANGE_ORDER_EXPORT.codename,
        ScgpPermissions.VIEW_DRAFT_ORDER.codename,
    ],
    ScgpUserRole.CS_MAINTAIN: [ScgpPermissions.MAINTAIN_ALT_MATERIAL.codename],
    ScgpUserRole.CUSTOMER_MATERIAL: [
        ScgpPermissions.MAINTAIN_CUSTOMER_MATERIAL.codename,
    ],
    ScgpUserRole.SHOPPING_DOMESTIC_PACKAGING: [
        ScgpPermissions.VIEW_ORDER_DOMESTIC.codename,
        ScgpPermissions.CREATE_ORDER_DOMESTIC_PACKAGING.codename,
        ScgpPermissions.CHANGE_ORDER_DOMESTIC.codename,
        ScgpPermissions.VIEW_DRAFT_ORDER.codename,
    ],
    ScgpUserRole.INQUIRY_DOMESTIC_ORDER_TRACK: [
        ScgpPermissions.VIEW_SALE_ORDER_TRACKING.codename,
        ScgpPermissions.VIEW_PENDING_ORDER_TRACKING.codename,
        ScgpPermissions.VIEW_ORDER_CONFIRM_REPORT.codename,
    ],
    ScgpUserRole.EXCEL_UPLOAD: [
        ScgpPermissions.MAINTAIN_EXCEL_UPLOAD.codename,
    ],
}

PERMISSION_CONFIG = {
    "View Stock": "scgp_view_stock",
    "Maintain User Group": "scgp_maintain_user_group",
    "All Upload Po Customer": "scgp_all_upload_po_customer",
    "Maintain Po Upload": "scgp_maintain_po_upload",
    "Create Order Customer": "scgp_create_order_customer",
    "Maintain User": "scgp_maintain_user",
    "Maintain Email Eo Upload": "scgp_maintain_email_eo_upload",
    "All Report Customer": "scgp_all_report_customer",
    "All Report Admin": "scgp_all_report_admin",
    "Maintain Organization": "scgp_maintain_organization",
    "View Order Export": "scgp_view_order_export",
    "Change Order Customer": "scgp_change_order_customer",
    "View Dummy": "scgp_view_dummy",
    "Change Order Export": "scgp_change_order_export",
    "All Contract": "scgp_all_contract",
    "Change Dummy": "scgp_change_dummy",
    "Maintain Role": "scgp_maintain_role",
    "Create Dummy": "scgp_create_dummy",
    "View Order Customer": "scgp_view_order_customer",
    "Change Order Domestic": "scgp_change_order_domestic",
    "Maintain Alt Material": "scgp_maintain_alt_material",
    "Maintain Customer Material": "scgp_maintain_customer_material",
    "View Draft Order": "scgp_view_draft_order",
    "All Upload Po Admin": "scgp_all_upload_po_admin",
    "Maintain Email": "scgp_maintain_email",
    "Create Order Domestic": "scgp_create_order_domestic",
    "View Order Domestic": "scgp_view_order_domestic",
    "Approve Dummy": "scgp_approve_dummy",
    "Maintain Role Permission": "scgp_maintain_role_permission",
    "Create Order Export": "scgp_create_order_export",
    "All Report Domestic": "scgp_all_report_domestic",
    "All Report Export": "scgp_all_report_export",
    "Create Order Domestic Packaging": "scgp_create_order_packaging_domestic",
    "View Pending Order Tracking": "scgp_view_pending_order_tracking",
    "View Sale Order Tracking": "scgp_view_sale_order_tracking",
    "View Order Confirm Report": "scgp_view_order_confirm",
    "Maintain Excel Upload": "scgp_maintain_excel_upload",
}

ROLE_MENU_FUNCTION_CONFIG = {
    ScgpUserRole.SHOPPING_DOMESTIC: {
        10: [
            {10: MenuFunctions.CREATE_ORDER_DOMESTIC.name},
            {20: MenuFunctions.SEARCH_CHANGE_ORDER_DOMESTIC.name},
            {30: MenuFunctions.REQUIRED_ATTENTION.name},
        ]
    },
    ScgpUserRole.SHOPPING_DOMESTIC_PACKAGING: {
        20: [
            {10: MenuFunctions.CREATE_ORDER_PACKAGING.name},
        ]
    },
    ScgpUserRole.SHOPPING_EXPORT: {
        30: [
            {10: MenuFunctions.CREATE_ORDER_EXPORT.name},
            {20: MenuFunctions.SEARCH_CHANGE_ORDER_EXPORT.name},
            {30: MenuFunctions.REQUIRED_ATTENTION.name},
        ]
    },
    ScgpUserRole.PO_UPLOAD: {
        40: [
            {10: MenuFunctions.PO_UPLOAD.name},
        ]
    },
    ScgpUserRole.EXCEL_UPLOAD: {
        50: [
            {10: MenuFunctions.EXCEL_UPLOAD.name},
        ]
    },
    ScgpUserRole.INQUIRY_DOMESTIC: {
        60: [
            {10: MenuFunctions.LIST_SALES_ORDER_REPORT.name},
            {20: MenuFunctions.PENDING_ORDER_REPORT.name},
            {30: MenuFunctions.ORDER_CONFIRMATION_REPORT.name},
            {40: MenuFunctions.DELIVERY_REPORT_LMS.name},
            {50: MenuFunctions.SALES_REPORT_KOS.name},
            {60: MenuFunctions.STOCK_ONHAND_REPORT.name},
            {70: MenuFunctions.IPLAN_REPORT.name},
        ]
    },
    ScgpUserRole.INQUIRY_DOMESTIC_ORDER_TRACK: {
        70: [
            {10: MenuFunctions.LIST_SALES_ORDER_REPORT_ORDER_TRACKING.name},
            {20: MenuFunctions.PENDING_ORDER_REPORT_ORDER_TRACKING.name},
            {30: MenuFunctions.ORDER_CONFIRMATION_REPORT.name},
            {40: MenuFunctions.DELIVERY_REPORT_LMS.name},
        ]
    },
    ScgpUserRole.INQUIRY_EXPORT: {
        80: [
            {10: MenuFunctions.LIST_SALES_ORDER_REPORT.name},
            {20: MenuFunctions.SALES_REPORT_KOS.name},
            {30: MenuFunctions.STOCK_ONHAND_REPORT.name},
            {40: MenuFunctions.IPLAN_REPORT.name},
        ]
    },
    ScgpUserRole.MAINTAIN: {
        90: [
            {10: MenuFunctions.ALTERNATED_MATERIAL.name},
            {20: MenuFunctions.USER_MANAGEMENT.name},
            {30: MenuFunctions.EMAIL_CONFIGURATION.name},
        ]
    },
    ScgpUserRole.CS_MAINTAIN: {
        100: [
            {10: MenuFunctions.ALTERNATED_MATERIAL.name},
            {20: MenuFunctions.EMAIL_CONFIGURATION.name},
        ]
    },
    ScgpUserRole.CUSTOMER_MATERIAL: {
        110: [
            {10: MenuFunctions.CUSTOMER_MATERIAL.name},
        ]
    },
    ScgpUserRole.SHOPPING_CUSTOMER: {
        120: [
            {10: MenuFunctions.CREATE_ORDER_CUSTOMER.name},
            {20: MenuFunctions.SEARCH_ORDER_CUSTOMER.name},
        ]
    },
    ScgpUserRole.PO_UPLOAD_CUSTOMER: {
        130: [
            {10: MenuFunctions.PO_UPLOAD.name},
        ]
    },
    ScgpUserRole.INQUIRY_CUSTOMER: {
        140: [
            {10: MenuFunctions.ORDER_CONFIRMATION_REPORT.name},
            {20: MenuFunctions.SEARCH_ORDER.name},
            {30: MenuFunctions.PENDING_ORDER_REPORT_CUSTOMER.name},
            {40: MenuFunctions.DELIVERY_REPORT_LMS.name},
            {50: MenuFunctions.EXTERNAL_LINK.name},
        ]
    },
}


def build_name(codename):
    return f"Can {codename.replace('_', ' ')}"


class Command(BaseCommand):
    help = "Create all groups, roles, and assign permissions"

    def handle(self, *args, **options):
        self.create_or_update_permissions()
        self.create_or_update_menufunctions()
        self.create_or_update_roles()
        self.create_or_update_group()

    def create_or_update_permissions(self):
        content_type, _ = ContentType.objects.get_or_create(
            app_label="scgp_user_management", model="scgpuser"
        )
        for name, codename in PERMISSION_CONFIG.items():
            permission, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                name=name,
            )

    def create_or_update_roles(self):
        for role_name in ROLE_PERMISSION_CONFIG:
            role_code = role_name.replace(" - ", " ").replace(" ", "_").upper()
            role, _ = Group.objects.get_or_create(name=role_name)
            scgp_role, _ = ScgpGroup.objects.get_or_create(
                code=role_code, defaults={"group_id": role.id}
            )
            self.assign_permissions_to_role(role)
            self.assign_menufunc_to_role(scgp_role, role)

    def create_or_update_group(self):
        for group_name in GROUP_ROLE_CONFIG:
            group, _ = ParentGroup.objects.get_or_create(
                name=group_name, defaults={"code": group_name.upper()}
            )
            self.assign_roles_to_group(group)

    def assign_roles_to_group(self, group: ParentGroup):
        role_names = GROUP_ROLE_CONFIG[group.name]
        roles = []
        for role_name in role_names:
            role = Group.objects.filter(name=role_name).first()
            roles.append(role)
        group.groups.clear()
        group.groups.set(roles)

    def assign_permissions_to_role(self, role: Group):
        codenames = ROLE_PERMISSION_CONFIG[role.name]
        permissions = []
        for codename in codenames:
            permission = Permission.objects.filter(codename=codename).first()
            permissions.append(permission)
        role.permissions.clear()
        role.permissions.set(permissions)

    def create_or_update_menufunctions(self):
        logging.info("Going to create menufunctions if not created")
        for menu_fun in MenuFunctions:
            menu, _ = MenuFunction.objects.get_or_create(
                code=menu_fun.name, defaults={"name": menu_fun.value}
            )
        logging.info("Completed Menu function creation")

    def assign_menufunc_to_role(self, scgp_role: ScgpGroup, role: Group):
        logging.info(
            f"Going to map user role and menufunctions for user role: {role.name}"
        )
        role_menus_conf = (
            ROLE_MENU_FUNCTION_CONFIG[role.name]
            if ROLE_MENU_FUNCTION_CONFIG.__contains__(role.name)
            else None
        )
        if role_menus_conf:
            for role_index, menu_list in role_menus_conf.items():
                for menu in menu_list:
                    for menu_index, menu_code in menu.items():
                        menu_func = MenuFunction.objects.filter(code=menu_code).first()
                        GroupMenuFunctions.objects.get_or_create(
                            menu_code=menu_func.code,
                            group_code=scgp_role.code,
                            defaults={
                                "menu_function_id": menu_func.id,
                                "group_id": role.id,
                                "menu_index": menu_index,
                                "group_index": role_index,
                            },
                        )
        logging.info(
            f"Completed user role and menufunctions mapping for user role: {role.name}"
        )
