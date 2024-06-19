from django.contrib.auth.models import Group
from django.db.models import Q, Subquery

from saleor.account.models import User

from sap_migration.models import (
    SoldToMaster,
    BusinessUnits,
    SalesOrganizationMaster,
    SalesGroupMaster,
    DistributionChannelMaster,
    DivisionMaster,
    SalesOfficeMaster,
)
from scgp_cip.common.constants import CIP
from scgp_user_management.graphql.helpers import (
    fullname_parse,
    get_bus_from_gdc_by_sale_orgs,
    get_sale_orgs_from_gdc,
)
from scgp_user_management.models import (
    ParentGroup,
    ScgpUser, MenuFunction, GroupMenuFunctions, ScgpGroup,
)

GDC_PLUGIN = "scg.gdc"


def resolve_parent_group(pk):
    return ParentGroup.objects.get(pk=pk)


def resolve_parent_groups():
    return ParentGroup.objects.all()


def resolve_groups_by_parent(pk):
    return Group.objects.filter(parent_groups__id=pk).order_by("name")


def resolve_sold_tos_by_user(user_id):
    return SoldToMaster.objects.filter(user__id=user_id)


def resolve_scgp_bus_by_user(root):
    if root.user_parent_group.name in ["Sales", "Section"]:
        return BusinessUnits.objects.all().order_by("code")
    return BusinessUnits.objects.filter(scgpuser__id=root.id).order_by("code")


def resolve_scgp_sales_organizations_by_user(root):
    if root.user_parent_group.name in ["Sales", "Section"]:
        return SalesOrganizationMaster.objects.all().order_by("code")
    return SalesOrganizationMaster.objects.filter(scgpuser__id=root.id).order_by("code")


def extract_sales_org_by_bu(sales_org_list):
    response_list = []
    bu_sales_org_dict = {}
    for sales_org in sales_org_list:
        bu_sales_org_dict.setdefault(sales_org.business_unit.code, []).append(sales_org)
    for key, values in bu_sales_org_dict.items():
        response_list.append({
            "business_unit": key,
            "sales_organizations": values
        })
    return response_list


def resolve_scgp_sales_organizations_by_bu_and_user(root):
    sales_org_list = SalesOrganizationMaster.objects.filter(scgpuser__id=root.id).order_by("code")
    response_list = extract_sales_org_by_bu(sales_org_list)
    return response_list


def resolve_scgp_sales_organizations_by_bu(root):
    sales_org_list = SalesOrganizationMaster.objects.all().order_by("code")
    response_list = extract_sales_org_by_bu(sales_org_list)
    return response_list


def resolve_scgp_sales_organizations_all():
    return SalesOrganizationMaster.objects.all().order_by("code")


def resolve_scgp_sales_groups_by_user(root):
    return SalesGroupMaster.objects.filter(scgpuser__id=root.id).order_by("code")


def resolve_scgp_distribution_channels_by_user(user_id):
    return DistributionChannelMaster.objects.filter(scgpuser__id=user_id)


def resolve_scgp_divisions_by_user(user_id):
    return DivisionMaster.objects.filter(scgpuser__id=user_id)


def resolve_scgp_sales_offices_by_user(user_id):
    return SalesOfficeMaster.objects.filter(scgpuser__id=user_id)


def resolve_sold_tos():
    return SoldToMaster.objects.all()


def resolve_user_extend_data(user_id):
    return ScgpUser.objects.filter(user__id=user_id).first()


def resolve_scgp_users():
    return User.objects.all()


def resolve_scgp_user(pk):
    return User.objects.filter(id=pk).first()


def resolve_filter_sold_to_scg_checkout():
    return SoldToMaster.objects.all()


def resolve_scgp_me(user):
    return User.objects.filter(id=user.id).first()


def resolve_default_business_unit(user_id):
    return BusinessUnits.objects.filter(scgpuser__id=user_id).order_by("name").first()


def resolve_default_sales_organizations(user_id):
    try:
        business_unit = BusinessUnits.objects.filter(scgpuser__id=user_id, name=CIP).first()
        return SalesOrganizationMaster.objects.filter(scgpuser__id=user_id, business_unit_id=business_unit.id).order_by(
            'code').first()
    except Exception:
        return None


def resolve_scgp_gdc_data(info, ad_user):
    manager = info.context.plugins
    user_details = manager.get_user_data_by_aduser(GDC_PLUGIN, ad_user)
    email = user_details["email"] or f"{ad_user}@scgp.mock"
    first_name, last_name = fullname_parse(user_details["e_FullName"])
    employee_id = user_details["empCode"] or ""

    sale_org_code = user_details["companyCode"]
    sale_orgs = get_sale_orgs_from_gdc(sale_org_code)
    bus = get_bus_from_gdc_by_sale_orgs(sale_orgs)

    response = {
        "employee_id": employee_id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "sale_orgs": sale_orgs,
        "bus": bus,
    }
    return response


def resolve_filter_sale_organization():
    return SalesOrganizationMaster.objects.all()


def resolve_filter_sales_group():
    return SalesGroupMaster.objects.all()


def resolve_filter_sale_office():
    return SalesOfficeMaster.objects.all()


def resolve_menu_function_by_group(group_id):
     result = GroupMenuFunctions.objects.filter(
        group_code__in=Subquery(ScgpGroup.objects.filter(group_id=group_id).values("code"))).order_by(
        "menu_index").select_related("menu_function")
     return [rs.menu_function for rs in result]


def resolve_groups_and_sort_by_index(pk):
    return Group.objects.filter(parent_groups__id=pk).distinct().order_by("group_menu__group_index")
