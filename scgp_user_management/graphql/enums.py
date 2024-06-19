import graphene

from scgp_user_management import error_codes as scgp_user_management_error_codes

ScgpUserManagementErrorCode = graphene.Enum.from_enum(scgp_user_management_error_codes.ScgpUserManagementErrorCode)

USER_BASE_FIELDS = {
    "email": "Email",
    "first_name": "First Name",
    "last_name": "Last Name",
}


class ScgpCustomerType(graphene.Enum):
    INTERNAL = "Internal"
    EXTERNAL = "External"


class ScgpUserStatus(graphene.Enum):
    FORCE_CHANGE_PASSWORD = "User must change password at first login."
    FORCE_ADD_EMAIL = "User must add email."


class ScgpUserInputFields(graphene.Enum):
    EXTRA_FIELDS = {
        **USER_BASE_FIELDS,
        "employee_id": "Employee ID",
        "scgp_bu_ids": "Business Unit",
        "scgp_sales_organization_ids": "Sale Organization",
        "scgp_sales_group_ids": "Sale Group",
        "scgp_distribution_channel_ids": "Distribute Channel",
        "scgp_division_ids": "Division",
        "scgp_sales_office_ids": "Sale Office",
        "sap_id": "Sap Id",
    }


class ScgpSaleUserInputFields(graphene.Enum):
    EXTRA_FIELDS = {
        **USER_BASE_FIELDS,
        "sale_id": "Sale ID",
        "employee_id": "Employee ID",
        "sap_id": "Sap Id",
    }


class ScgpSectionUserInputFields(graphene.Enum):
    EXTRA_FIELDS = {
        **USER_BASE_FIELDS,
        "employee_id": "Employee ID",
        "sap_id": "Sap Id",
    }


class ScgpCustomerUserInputFields(graphene.Enum):
    EXTRA_FIELDS = {
        **USER_BASE_FIELDS,
        "customer_type": "Customer Type",
        "company_email": "Company Email",
        "display_name": "Display Name",
        "sold_to_ids": "Sold To",
        "sap_id": "Sap Id",
    }
