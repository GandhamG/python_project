import pandas as pd

from saleor.account.models import (
    User,
    Group,
)
from scgp_user_management.models import (
    ScgpUser,
    ParentGroup,
    ScgpUserLanguage,
)
from sap_migration.models import (
    SoldToMaster,
    BusinessUnits,
    SalesOrganizationMaster,
    SalesGroupMaster,
    DistributionChannelMaster,
    DivisionMaster,
    SalesOfficeMaster,
)

from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth.hashers import make_password

from scgp_user_management.error_codes import ScgpUserManagementErrorCode

MAX_UPLOAD_KB = 10 * 1024 * 1024

# Shared Fields
USER_EMAIL = "Email"
USER_COMPANY_EMAIL = "Company Email"
USER_FIRST_NAME = "First name"
USER_LAST_NAME = "Last name"
USER_LANGUAGE = "Language"
USER_GROUP = "User Group"
USER_ROLES = "User Roles"

# Customer Sheet Fields
CUSTOMER_SHEET_NAME = "Customer"
CUSTOMER_TYPE = "Customer Type"
CUSTOMER_USERNAME = "Existing User id / AD User"
CUSTOMER_SOLD_TO = "Sold to"
CUSTOMER_DISPLAY_NAME = "Display name"
CUSTOMER_ALL_TITLES = [
    CUSTOMER_TYPE,
    CUSTOMER_USERNAME,
    USER_EMAIL,
    USER_COMPANY_EMAIL,
    CUSTOMER_SOLD_TO,
    USER_FIRST_NAME,
    USER_LAST_NAME,
    CUSTOMER_DISPLAY_NAME,
    USER_LANGUAGE,
    USER_GROUP,
    USER_ROLES
]

# Internal User Sheet Fields
INTERNAL_USER_SHEET_NAME = "Internal User"
INTERNAL_USER_AD_USER = "AD User"
INTERNAL_USER_EMP_ID = "Emp id"
INTERNAL_USER_BU = "BU"
INTERNAL_USER_SALE_ORG = "Sale Org"
INTERNAL_USER_DISTRIBUTION_CHANNEL = "Distribution Chanel"
INTERNAL_USER_DIVISION = "Division"
INTERNAL_USER_SALE_OFFICE = "Sale Office"
INTERNAL_USER_SALE_GROUP = "Sale Group"
INTERNAL_USER_ALL_TITLE = [
    INTERNAL_USER_AD_USER,
    INTERNAL_USER_EMP_ID,
    USER_EMAIL,
    USER_FIRST_NAME,
    USER_LAST_NAME,
    USER_LANGUAGE,
    INTERNAL_USER_BU,
    INTERNAL_USER_SALE_ORG,
    INTERNAL_USER_DISTRIBUTION_CHANNEL,
    INTERNAL_USER_DIVISION,
    INTERNAL_USER_SALE_OFFICE,
    INTERNAL_USER_SALE_GROUP,
    USER_GROUP,
    USER_ROLES
]


def get_set_of_ad_user():
    return set(ScgpUser.objects.exclude(ad_user__isnull=True).exclude(ad_user__exact='').values_list('ad_user', flat=True))


def get_set_of_username():
    return set(ScgpUser.objects.exclude(username__isnull=True).exclude(username__exact='').values_list('username', flat=True))


def get_set_of_email():
    return set(User.objects.exclude(email__isnull=True).exclude(email__exact='').values_list('email', flat=True))


def create_base_user(row, groups, is_customer=True):
    hashed_password = make_password(row[CUSTOMER_USERNAME]) if is_customer else ""

    user = User.objects.create(
        email=row[USER_EMAIL] if isinstance(row[USER_EMAIL], str) else f"{row[CUSTOMER_USERNAME]}@scgp.mock",
        first_name=row[USER_FIRST_NAME],
        last_name=row[USER_LAST_NAME],
        password=hashed_password,
        is_staff=True,
        is_active=True
    )
    user.groups.set(groups)
    return user


@transaction.atomic
def create_customer(
    row,
    parent_group,
    groups,
    sold_to,
    languages,
    current_user,
):
    user = create_base_user(row, groups, True)
    user.master_sold_to.set(sold_to)

    user_extend = ScgpUser.objects.create(
        user=user,
        customer_type=row[CUSTOMER_TYPE],
        username=row[CUSTOMER_USERNAME],
        company_email=row[USER_COMPANY_EMAIL],
        display_name=row[CUSTOMER_DISPLAY_NAME] if isinstance(row[CUSTOMER_DISPLAY_NAME], str) else row[
            CUSTOMER_USERNAME],
        created_by=current_user,
        updated_by=current_user,
        user_parent_group=parent_group
    )
    user_extend.languages.set(languages)


def import_customer(
    df,
    error_logs,
    current_user,
    current_username_set,
    current_email_set
):
    for index, row in df.iterrows():
        line = index + 2
        if not(row[CUSTOMER_TYPE]) or isinstance(row[CUSTOMER_TYPE], float):
            error_logs += f"\nLine {line}: {CUSTOMER_TYPE} cannot be blank"
            continue
        if not(row[CUSTOMER_USERNAME]) or isinstance(row[CUSTOMER_USERNAME], float):
            error_logs += f"\nLine {line}: {CUSTOMER_USERNAME} cannot be blank"
            continue
        if row[CUSTOMER_USERNAME] in current_username_set:
            error_logs += f"\nLine {line}: {CUSTOMER_USERNAME} {row[CUSTOMER_USERNAME]} has been used"
            continue
        if row[USER_EMAIL] in current_email_set:
            error_logs += f"\nLine {line}: {USER_EMAIL} {row[USER_EMAIL]} has been used"
            continue
        if not(row[USER_COMPANY_EMAIL]) or isinstance(row[USER_COMPANY_EMAIL], float):
            error_logs += f"\nLine {line}: {USER_COMPANY_EMAIL} cannot be blank"
            continue
        if not(row[CUSTOMER_SOLD_TO]) or isinstance(row[CUSTOMER_SOLD_TO], float):
            error_logs += f"\nLine {line}: {CUSTOMER_SOLD_TO} cannot be blank"
            continue
        if not(row[USER_FIRST_NAME]) or isinstance(row[USER_FIRST_NAME], float):
            error_logs += f"\nLine {line}: {USER_FIRST_NAME} cannot be blank"
            continue
        if not(row[USER_LAST_NAME]) or isinstance(row[USER_LAST_NAME], float):
            error_logs += f"\nLine {line}: {USER_LAST_NAME} cannot be blank"
            continue
        if not(row[USER_GROUP]) or isinstance(row[USER_GROUP], float):
            error_logs += f"\nLine {line}: {USER_GROUP} cannot be blank"
            continue
        if not(row[USER_ROLES]) or isinstance(row[USER_ROLES], float):
            error_logs += f"\nLine {line}: {USER_ROLES} cannot be blank"
            continue

        parent_group = ParentGroup.objects.filter(name=row[USER_GROUP]).first()
        if not parent_group:
            error_logs += f"\nLine {line}: wrong {USER_GROUP}"
            continue

        if row[USER_ROLES] == "All":
            groups = parent_group.groups.all()
        else:
            group_names = [x.strip() for x in row[USER_ROLES].split(",")]
            groups = Group.objects.filter(name__in=group_names)
            if len(group_names) != len(group_names):
                error_logs += f"\nLine {line}: wrong {USER_ROLES}"
                continue

        sold_to_code = (
            row[CUSTOMER_SOLD_TO].zfill(10)
            if len(row[CUSTOMER_SOLD_TO]) < 10
            else row[CUSTOMER_SOLD_TO]
        )
        sold_to = SoldToMaster.objects.filter(sold_to_code=sold_to_code)
        if not sold_to:
            error_logs += f"\nLine {line}: wrong {CUSTOMER_SOLD_TO}"
            continue

        language_codes = [x.strip() for x in row[USER_LANGUAGE].split(",")]
        languages = ScgpUserLanguage.objects.filter(code__in=language_codes)
        if len(languages) != len(language_codes):
            error_logs += f"\nLine {line}: wrong {USER_LANGUAGE}"
            continue

        try:
            create_customer(
                row,
                parent_group,
                groups,
                sold_to,
                languages,
                current_user,
            )
            error_logs += f"\nLine {line}: import done"
        except Exception as e:
            error_logs += f"\nLine {line}: {e}"

    return error_logs


def create_internal_user(
    row,
    parent_group,
    groups,
    languages,
    current_user,
    bu,
    sale_org,
    distribution_channel,
    division,
    sale_office,
    sale_group
):
    user = create_base_user(row, groups, False)

    user_extend = ScgpUser.objects.create(
        user=user,
        ad_user=row[INTERNAL_USER_AD_USER],
        employee_id=row[INTERNAL_USER_EMP_ID] if isinstance(row[INTERNAL_USER_EMP_ID], str) else "",
        created_by=current_user,
        updated_by=current_user,
        user_parent_group=parent_group
    )
    user_extend.scgp_bus.set(bu)
    user_extend.scgp_sales_organizations.set(sale_org)
    user_extend.scgp_sales_groups.set(sale_group)
    user_extend.scgp_distribution_channels.set(distribution_channel)
    user_extend.scgp_divisions.set(division)
    user_extend.scgp_sales_offices.set(sale_office)

    user_extend.languages.set(languages)


def import_internal_user(
    df,
    error_logs,
    current_user,
    current_ad_user_set,
    current_email_set
):
    for index, row in df.iterrows():
        line = index + 2
        if not(row[INTERNAL_USER_AD_USER]):
            error_logs += f"\nLine {line}: {INTERNAL_USER_AD_USER} cannot be blank"
            continue
        if row[INTERNAL_USER_AD_USER] in current_ad_user_set:
            error_logs += f"\nLine {line}: {INTERNAL_USER_AD_USER} {row[INTERNAL_USER_AD_USER]} has been used"
            continue
        if not (row[USER_EMAIL]):
            error_logs += f"\nLine {line}: {USER_EMAIL} cannot be blank"
            continue
        if row[USER_EMAIL] in current_email_set:
            error_logs += f"\nLine {line}: {USER_EMAIL} {row[USER_EMAIL]} has been used"
            continue
        if not(row[USER_FIRST_NAME]):
            error_logs += f"\nLine {line}: {USER_FIRST_NAME} cannot be blank"
            continue
        if not(row[USER_LAST_NAME]):
            error_logs += f"\nLine {line}: {USER_LAST_NAME} cannot be blank"
            continue
        if not(row[INTERNAL_USER_BU]):
            error_logs += f"\nLine {line}: {INTERNAL_USER_BU} cannot be blank"
            continue
        if not(row[INTERNAL_USER_SALE_ORG]):
            error_logs += f"\nLine {line}: {INTERNAL_USER_SALE_ORG} cannot be blank"
            continue
        if not(row[INTERNAL_USER_DISTRIBUTION_CHANNEL]):
            error_logs += f"\nLine {line}: {INTERNAL_USER_DISTRIBUTION_CHANNEL} cannot be blank"
            continue
        if not(row[INTERNAL_USER_DIVISION]):
            error_logs += f"\nLine {line}: {INTERNAL_USER_DIVISION} cannot be blank"
            continue
        if not(row[INTERNAL_USER_SALE_OFFICE]):
            error_logs += f"\nLine {line}: {INTERNAL_USER_SALE_OFFICE} cannot be blank"
            continue
        if not(row[INTERNAL_USER_SALE_GROUP]):
            error_logs += f"\nLine {line}: {INTERNAL_USER_SALE_GROUP} cannot be blank"
            continue
        if not(row[USER_GROUP]):
            error_logs += f"\nLine {line}: {USER_GROUP} cannot be blank"
            continue
        if not(row[USER_ROLES]):
            error_logs += f"\nLine {line}: {USER_ROLES} cannot be blank"
            continue

        parent_group = ParentGroup.objects.filter(name=row[USER_GROUP]).first()
        if not parent_group:
            error_logs += f"\nLine {line}: wrong {USER_GROUP}"
            continue

        if row[USER_ROLES] == "All":
            groups = parent_group.groups.all()
        else:
            group_names = [x.strip() for x in row[USER_ROLES].split(",")]
            groups = Group.objects.filter(name__in=group_names)
            if len(group_names) != len(group_names):
                error_logs += f"\nLine {line}: wrong {USER_ROLES}"
                continue

        bu_names = [x.strip() for x in row[INTERNAL_USER_BU].split(",")]
        bu = BusinessUnits.objects.filter(name__in=bu_names)
        if len(bu) != len(bu_names):
            error_logs += f"\nLine {line}: wrong {INTERNAL_USER_BU}"
            continue

        sale_org_codes = [x.strip() for x in row[INTERNAL_USER_SALE_ORG].split(",")]
        sale_org = SalesOrganizationMaster.objects.filter(code__in=sale_org_codes)
        if len(sale_org) != len(sale_org_codes):
            error_logs += f"\nLine {line}: wrong {INTERNAL_USER_SALE_ORG}"
            continue

        distribution_channel_codes = [x.strip() for x in row[INTERNAL_USER_DISTRIBUTION_CHANNEL].split(",")]
        distribution_channel = DistributionChannelMaster.objects.filter(code__in=distribution_channel_codes)
        if len(distribution_channel) != len(distribution_channel_codes):
            error_logs += f"\nLine {line}: wrong {INTERNAL_USER_DISTRIBUTION_CHANNEL}"
            continue

        division_codes = [x.strip() for x in row[INTERNAL_USER_DIVISION].split(",")]
        division = DivisionMaster.objects.filter(code__in=division_codes)
        if len(division) != len(division_codes):
            error_logs += f"\nLine {line}: wrong {INTERNAL_USER_DIVISION}"
            continue

        sale_office_codes = [x.strip() for x in row[INTERNAL_USER_SALE_OFFICE].split(",")]
        sale_office = SalesOfficeMaster.objects.filter(code__in=sale_office_codes)
        if len(sale_office) != len(sale_office_codes):
            error_logs += f"\nLine {line}: wrong {INTERNAL_USER_SALE_OFFICE}"
            continue

        sale_group_codes = [x.strip() for x in row[INTERNAL_USER_SALE_GROUP].split(",")]
        sale_group = SalesGroupMaster.objects.filter(code__in=sale_group_codes)
        if len(sale_group) != len(sale_group_codes):
            error_logs += f"\nLine {line}: wrong {INTERNAL_USER_SALE_GROUP}"
            continue

        language_codes = [x.strip() for x in row[USER_LANGUAGE].split(",")]
        languages = ScgpUserLanguage.objects.filter(code__in=language_codes)
        if len(languages) != len(language_codes):
            error_logs += f"\nLine {line}: wrong {USER_LANGUAGE}"
            continue

        try:
            create_internal_user(
                row,
                parent_group,
                groups,
                languages,
                current_user,
                bu,
                sale_org,
                distribution_channel,
                division,
                sale_office,
                sale_group
            )
            error_logs += f"\nLine {line}: import done"
        except Exception as e:
            error_logs += f"\nLine {line}: {e}"

    return error_logs


@transaction.atomic
def scgp_user_mapping_data(file_data, current_user):
    error_logs = "Import user logs"

    if not file_data:
        raise ValidationError(
            {
                "file": ValidationError(
                    "No files have been uploaded.",
                    code=ScgpUserManagementErrorCode.REQUIRED.value,
                )
            }
        )
    if file_data.size > MAX_UPLOAD_KB:
        raise ValidationError(
            {
                "file_size": ValidationError(
                    "File size is not over 10MB.",
                    code=ScgpUserManagementErrorCode.INVALID.value,
                )
            }
        )
    if file_data.name[-5:] != ".xlsx":
        raise ValidationError(
            {
                "file_type": ValidationError(
                    "Only support .xlsx file type. Please try again",
                    code=ScgpUserManagementErrorCode.INVALID.value,
                )
            }
        )

    df_customer = pd.read_excel(file_data, CUSTOMER_SHEET_NAME, dtype=str)
    if not list(df_customer.columns) == CUSTOMER_ALL_TITLES:
        raise ValidationError(
            {
                "file": ValidationError(
                    "Please input right format file!",
                    code=ScgpUserManagementErrorCode.INVALID.value,
                )
            }
        )
    df_internal_user = pd.read_excel(file_data, INTERNAL_USER_SHEET_NAME, dtype=str)
    if not list(df_internal_user.columns) == INTERNAL_USER_ALL_TITLE:
        raise ValidationError(
            {
                "file": ValidationError(
                    "Please input right format file!",
                    code=ScgpUserManagementErrorCode.INVALID.value,
                )
            }
        )

    current_email_set = get_set_of_email()
    current_username_set = get_set_of_username()
    current_ad_user_set = get_set_of_ad_user()

    error_logs += "\nImporting Customer..."
    error_logs = import_customer(
        df_customer,
        error_logs,
        current_user,
        current_username_set,
        current_email_set
    )

    error_logs += "\nImporting Internal User..."
    error_logs = import_internal_user(
        df_internal_user,
        error_logs,
        current_user,
        current_ad_user_set,
        current_email_set
    )

    return error_logs
