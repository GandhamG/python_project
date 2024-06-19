from typing import List, Tuple, TypedDict

from django.db import transaction
from django.db.models.manager import BaseManager
from django.http import HttpRequest, JsonResponse
from django.http.request import QueryDict
from pandas.io.excel import read_excel

import sap_migration.models as migration_models
from saleor.account.models import User
from saleor.plugins.manager import get_plugins_manager
from sap_master_data.models import SoldToMaster
from scgp_user_management.implementations.scgp_users import (
    create_or_update_user_base,
    get_user_m2m_fields_input_by_group,
    handler_user_m2m_fields,
)
from scgp_user_management.models import ParentGroup, ScgpUser

from .decorators import request_method, require_internal_token

# ---------------CONSTANT-----------------

CONFIG_PREFIX = "cfg_"
UPLOAD_USER_TOKEN = "scguploaduser"

# ---------------Class stuff----------
class ExternalUser(TypedDict):
    customer_type: str
    ad_user: str
    email: str
    company_email: str
    sold_to: str
    first_name: str
    last_name: str
    display_name: str
    user_group: str
    user_roles: str


class InternalUser(TypedDict):
    ad_user: str
    emp_id: str
    email: str
    first_name: str
    last_name: str
    language: str
    business_unit: str
    sale_organizations: str
    distribution_channel: str
    division: str
    sale_offices: str
    sale_groups: str
    user_group: str
    user_roles: str
    sale_id: str


# --------------Helpers-------------------


def parse_config(request_body: QueryDict) -> dict:
    config = {}

    for key, value in request_body.items():
        if key.startswith(CONFIG_PREFIX):
            config[key[len(CONFIG_PREFIX) :]] = value

    return config


def _parse_fn_parameter_internal(
    user: InternalUser, master_data: dict
) -> Tuple[bool, dict]:
    ad_user = user.get("ad_user")
    if not ad_user:
        return False, {
            "email": user.get("email"),
            "error": "AD USER not found in file",
        }
    parent_group_name = user.get("user_group")
    user_parent_group = ParentGroup.objects.filter(name=parent_group_name).first()
    employee_id = user.get("emp_id", "")
    sale_id = user.get("sale_id", "")
    if not user_parent_group:
        return False, {
            "email": user.get("email"),
            "error": f'User group "{parent_group_name}" not found',
        }
    auth_groups_dict = {item.name: item.id for item in user_parent_group.groups.all()}
    if (roles := user.get("user_roles", "")) == "All":
        group_ids = list(auth_groups_dict.values())
    else:
        group_names = roles.split(",")
        failed_group_name = None
        group_ids = []
        for name in group_names:
            group_id = auth_groups_dict.get(name)
            if not group_id:
                failed_group_name = name
                break
            else:
                group_ids.append(group_id)
        if failed_group_name:
            return False, {
                "email": user.get("email"),
                "error": f"No user roles found with name {failed_group_name} for group {user_parent_group.name}",
            }
        group_ids = [
            auth_groups_dict.get(name)
            for name in group_names
            if auth_groups_dict.get(name) is not None
        ]
    business_unit_mst: BaseManager[migration_models.BusinessUnits] = master_data.get(
        "business_unit_mst"
    )

    if (business_units_in := user.get("business_unit", "")) == "All":
        business_units = business_unit_mst
    else:
        bus_unit_names = business_units_in.strip().split(",")
        business_units = business_unit_mst.filter(name__in=bus_unit_names)

    if not business_units:
        return False, {
            "email": user.get("email"),
            "error": f"""Business Unit \"{user.get("business_unit", "")}\" not found""",
        }
    sale_org_mst: BaseManager[
        migration_models.SalesOrganizationMaster
    ] = master_data.get("sale_organization_mst")
    if (sale_organizations := user.get("sale_organizations", "")) == "All":
        sale_org_ids = list(
            sale_org_mst.filter(business_unit__in=business_units).values_list(
                "id", flat=True
            )
        )
    else:
        sale_org_names = sale_organizations.split(",")
        sale_org_ids = list(
            sale_org_mst.filter(
                business_unit__in=business_units, name__in=sale_org_names
            ).values_list("id", flat=True)
        )

    sale_group_mst: BaseManager[migration_models.SalesGroupMaster] = master_data.get(
        "sale_group_mst"
    )
    sale_group_id = []
    if user.get("sale_groups", "") == "All":
        sale_group_id = list(
            sale_group_mst.filter(sales_organization_id__in=sale_org_ids).values_list(
                "id", flat=True
            )
        )

    distribution_mst: BaseManager[
        migration_models.DistributionChannelMaster
    ] = master_data.get("distribution_channel_mst")
    distribution_codes = str(user.get("distribution_channel", "")).split(",")
    distribution_ids = list(
        distribution_mst.filter(code__in=distribution_codes)
        .values_list("id", flat=True)
        .all()
    )

    sale_office_mst: BaseManager[migration_models.SalesOfficeMaster] = master_data.get(
        "sale_office_mst"
    )
    if (sale_offices := user.get("sale_offices", "")) == "All":
        sale_office_ids = sale_office_mst.filter(sales_organization_id__in=sale_org_ids)
    else:
        sale_office_code = sale_offices.split(",")
        sale_office_ids = sale_office_mst.filter(
            sale_organization_id__in=sale_org_ids, code__in=sale_office_code
        )

    division_mst: BaseManager[migration_models.DivisionMaster] = master_data.get(
        "division_mst"
    )
    division = division_mst.filter(code=str(user.get("division")).zfill(2)).first()
    if not division:
        return False, {
            "email": user.get("email"),
            "error": f"""Division \"{user.get("division")}\" not found""",
        }
    params = {
        "user_parent_group_id": user_parent_group.pk,
        "email": user.get("email"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "employee_id": employee_id,
        "sale_id": sale_id,
        "ad_user": ad_user,
        "group_ids": group_ids,
    }
    if parent_group_name not in ["Sales", "Section", "Customer"]:
        params = {
            **params,
            "scgp_bu_ids": [bu.pk for bu in business_units],
            "scgp_sales_organization_ids": sale_org_ids,
            "scgp_sales_group_ids": sale_group_id,
            "scgp_distribution_channel_ids": distribution_ids,
            "scgp_division_ids": [division.pk],
            "scgp_sales_office_ids": sale_office_ids,
        }
    return True, params


def create_internal_user(user_list: List[InternalUser]):
    c_success = 0
    c_failed = 0
    failed_accounts = []
    master_data = {
        "parent_group_mst": ParentGroup.objects.prefetch_related("groups").all(),
        "business_unit_mst": migration_models.BusinessUnits.objects.all(),
        "sale_organization_mst": migration_models.SalesOrganizationMaster.objects.all(),
        "distribution_channel_mst": migration_models.DistributionChannelMaster.objects.all(),
        "division_mst": migration_models.DivisionMaster.objects.all(),
        "sale_office_mst": migration_models.SalesOfficeMaster.objects.all(),
        "sale_group_mst": migration_models.SalesGroupMaster.objects.all(),
    }

    for user in user_list:
        success, value = _parse_fn_parameter_internal(user, master_data)
        if not success:
            c_failed += 1
            failed_accounts.append(value)
            continue
        with transaction.atomic():
            try:
                cur_user = User.objects.filter(email=user.get("email")).first()
                if cur_user:
                    cur_user.delete()
                user_base: User = create_or_update_user_base(
                    value, parent_group=user.get("user_group"), user=None
                )
                user_base.set_password(user.get("ad_user"))
                # force check password
                # user_base.last_login = datetime.datetime.now()
                user_base.save()
                user_base.refresh_from_db()
                scg_user = ScgpUser.objects.filter(user=user_base)
                if scg_user:
                    scg_user.delete()

                m2m_fields = get_user_m2m_fields_input_by_group(
                    value, user.get("user_group")
                )
                new_user = ScgpUser.objects.create(
                    user=user_base,
                    **value,
                )

                handler_user_m2m_fields(new_user, m2m_fields)
                c_success += 1
            except Exception as e:
                failed_accounts.append(
                    {
                        "email": user.get("email"),
                        "error": str(e),
                    }
                )
                c_failed += 1
                transaction.set_rollback(True)
    return {
        "success": c_success,
        "failed": c_failed,
        "failed_accounts": failed_accounts,
    }


def create_external_customers(external_user_list: List[ExternalUser]):
    c_success = 0
    c_failed = 0
    failed_account = []
    sold_to_codes = list(
        map(lambda user: str(user.get("sold_to", "")).zfill(10), external_user_list)
    )
    list_sold_to_dict = {
        item.sold_to_code: item.pk
        for item in SoldToMaster.objects.filter(sold_to_code__in=sold_to_codes).all()
    }
    parent_group_dict = {item.name: item for item in ParentGroup.objects.all()}
    for user in external_user_list:
        # There could be a case user doesn't have ad user id on gdc
        ad_user = user.get("ad_user")
        if not ad_user:
            failed_account.append(
                {
                    "email": user.get("email"),
                    "error": "AD USER not found in file",
                }
            )
            c_failed += 1
            continue
        sold_to_id = list_sold_to_dict.get(str(user.get("sold_to", "")).zfill(10))
        if not sold_to_id:
            failed_account.append(
                {
                    "email": user.get("email"),
                    "error": "Sold to code not found",
                }
            )
            c_failed += 1
            continue
        parent_group = parent_group_dict.get(user.get("user_group"))
        if not parent_group:
            c_failed += 1
            failed_account.append(
                {
                    "email": user.get("email"),
                    "error": "No user group found",
                }
            )
            continue
        auth_groups_dict = {item.name: item.id for item in parent_group.groups.all()}
        group_ids = []
        if user.get("user_roles", "").lower() == "all":
            group_ids = list(auth_groups_dict.values())
        else:
            group_names = user.get("user_roles", "").split(",")
            failed_group_name = None
            for name in group_names:
                group_id = auth_groups_dict.get(name)
                if not group_id:
                    failed_group_name = name
                    break
                else:
                    group_ids.append(group_id)
            if failed_group_name:
                c_failed += 1
                failed_account.append(
                    {
                        "email": user.get("email"),
                        "error": f"No user roles found with name {failed_group_name} for group {parent_group.name}",
                    }
                )
                continue
            group_ids = [
                auth_groups_dict.get(name)
                for name in group_names
                if auth_groups_dict.get(name) is not None
            ]
        fn_parameter = {
            "user_parent_group_id": parent_group.pk,
            "email": user.get("email"),
            "username": user.get("email"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "ad_user": ad_user,
            "group_ids": group_ids,
            "customer_type": user.get("customer_type", ""),
            "company_email": user.get("email"),
            "sold_to_ids": [sold_to_id],
        }
        with transaction.atomic():
            try:
                cur_user = User.objects.filter(email=user.get("email")).first()
                if cur_user:
                    cur_user.delete()
                user_base: User = create_or_update_user_base(
                    fn_parameter, parent_group=user.get("user_group"), user=None
                )
                user_base.set_password(ad_user)
                user_base.language_code = user.get("language_code", "EN").lower()
                # force check password
                # user_base.last_login = datetime.datetime.now()
                user_base.save()
                user_base.refresh_from_db()
                scg_user = ScgpUser.objects.filter(user=user_base)
                if scg_user:
                    scg_user.delete()
                ScgpUser.objects.create(
                    user=user_base,
                    **fn_parameter,
                )
                c_success += 1
            except Exception as e:
                failed_account.append(
                    {
                        "email": user.get("email"),
                        "error": str(e),
                    }
                )
                c_failed += 1
                transaction.set_rollback(True)

    return {"success": c_success, "failed": c_failed, "failed_account": failed_account}


def _check_enable_upload_user():
    manager = get_plugins_manager()
    _plugin = manager.get_plugin("scg.settings")
    config = _plugin.config
    return config.enable_upload_user or False


@request_method("POST")
@require_internal_token
def upload_user_data(request: HttpRequest) -> JsonResponse:
    is_enabled = _check_enable_upload_user()
    if not is_enabled:
        return JsonResponse(
            data={"message": "Upload user is disabled.", "success": False}
        )
    excel_file = request.FILES.get("file")
    if not excel_file:
        return JsonResponse(data={"message": "File Not Found", "success": False})
    external_customer_sheet = read_excel(
        excel_file.file, sheet_name="External Customer", keep_default_na=False
    )
    internal_user_sheet = read_excel(
        excel_file.file, sheet_name="Internal User", keep_default_na=False
    )

    external_user_list: List[ExternalUser] = []
    for _index, row in external_customer_sheet[0:].iterrows():
        external_user_list.append(
            {
                "customer_type": row[0],
                "ad_user": row[1],
                "email": row[2],
                "company_email": row[3],
                "sold_to": row[4],
                "first_name": row[5],
                "last_name": row[6],
                "display_name": row[7],
                "language_code": row[8],
                "user_group": row[9],
                "user_roles": row[10],
            }
        )

    external_user_response = create_external_customers(external_user_list)

    internal_user_list: List[InternalUser] = []
    for _, row in internal_user_sheet[0:].iterrows():
        internal_user_list.append(
            {
                "ad_user": row[0],
                "emp_id": row[1],
                "email": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "language": row[5],
                "business_unit": row[6],
                "sale_organizations": row[7],
                "distribution_channel": row[8],
                "division": row[9],
                "sale_offices": row[10],
                "sale_groups": row[11],
                "user_group": row[12],
                "user_roles": row[13],
                "sale_id": row[14],
            }
        )
    internal_user_response = create_internal_user(internal_user_list)
    return JsonResponse(
        {
            "external_customers": external_user_response,
            "internal_users": internal_user_response,
        }
    )
