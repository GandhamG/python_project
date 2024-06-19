import graphene
from saleor.account.models import (
    User as UserModel,
    Group as GroupModel,
)
from saleor.graphql.account.types import User, Group
from saleor.graphql.core.connection import CountableConnection
from saleor.graphql.core.types import ModelObjectType

from sap_migration.graphql.types import (
    BusinessUnits,
    SalesOrganizationMaster,
    SalesGroupMaster,
    DistributionChannelMaster,
    DivisionMaster,
    SalesOfficeMaster,
    SoldToMaster,
)
from scg_checkout.graphql.types import ScgCountableConnection
from scgp_user_management import models
from scgp_user_management.graphql.resolvers.scgp_users import (
    resolve_sold_tos_by_user,
    resolve_scgp_bus_by_user,
    resolve_scgp_sales_organizations_by_user,
    resolve_scgp_sales_groups_by_user,
    resolve_scgp_distribution_channels_by_user,
    resolve_scgp_divisions_by_user,
    resolve_scgp_sales_offices_by_user,
    resolve_groups_by_parent,
    resolve_user_extend_data, resolve_default_business_unit, resolve_default_sales_organizations,
    resolve_scgp_sales_organizations_all, resolve_scgp_sales_organizations_by_bu_and_user,
    resolve_scgp_sales_organizations_by_bu, resolve_menu_function_by_group, resolve_groups_and_sort_by_index,
)
from scgp_user_management.models import MenuFunction


class ScgpGroup(Group):
    id = graphene.ID()

    class Meta:
        description = "Scgp Group."
        model = GroupModel


class ParentGroup(ModelObjectType):
    id = graphene.ID()
    name = graphene.String()
    code = graphene.String()
    groups = graphene.List(ScgpGroup, description="List of role group ")
    description = graphene.String()

    class Meta:
        model = models.ParentGroup

    @staticmethod
    def resolve_groups(root, info):
        return resolve_groups_by_parent(root.id)


class ParentGroupCountableConnection(CountableConnection):
    class Meta:
        node = ParentGroup


class SalesOrgByBu(graphene.ObjectType):
    business_unit = graphene.String()
    sales_organizations = graphene.List(SalesOrganizationMaster)


class ScgpUserExtend(ModelObjectType):
    id = graphene.ID()
    user_parent_group = graphene.Field(ParentGroup)

    ad_user = graphene.String()
    employee_id = graphene.String()
    sale_id = graphene.String()
    customer_type = graphene.String()
    company_email = graphene.String()
    display_name = graphene.String()
    username = graphene.String()

    scgp_bus = graphene.List(BusinessUnits)
    scgp_sales_organizations = graphene.List(SalesOrganizationMaster)
    scgp_sales_organizations_all = graphene.List(SalesOrganizationMaster)
    scgp_sales_groups = graphene.List(SalesGroupMaster)
    scgp_distribution_channels = graphene.List(DistributionChannelMaster)
    scgp_divisions = graphene.List(DivisionMaster)
    scgp_sales_offices = graphene.List(SalesOfficeMaster)
    default_business_unit = graphene.Field(BusinessUnits)
    default_sales_organizations = graphene.Field(SalesOrganizationMaster)
    created_by = graphene.Field(User)
    updated_by = graphene.Field(User)
    updated_at = graphene.DateTime()
    sap_id = graphene.String()
    sales_org_by_bu_and_user = graphene.List(SalesOrgByBu)
    sales_org_by_bu = graphene.List(SalesOrgByBu)

    class Meta:
        description = "ScgpUser extend data."
        model = models.ScgpUser

    @staticmethod
    def resolve_scgp_bus(root, info):
        return resolve_scgp_bus_by_user(root)

    @staticmethod
    def resolve_scgp_sales_organizations(root, info):
        return resolve_scgp_sales_organizations_by_user(root)

    @staticmethod
    def resolve_scgp_sales_organizations_all(root, info):
        return resolve_scgp_sales_organizations_all()

    @staticmethod
    def resolve_scgp_sales_groups(root, info):
        return resolve_scgp_sales_groups_by_user(root)

    @staticmethod
    def resolve_scgp_distribution_channels(root, info):
        return resolve_scgp_distribution_channels_by_user(root.id)

    @staticmethod
    def resolve_scgp_divisions(root, info):
        return resolve_scgp_divisions_by_user(root.id)

    @staticmethod
    def resolve_scgp_sales_offices(root, info):
        return resolve_scgp_sales_offices_by_user(root.id)

    @staticmethod
    def resolve_default_business_unit(root, info):
        return resolve_default_business_unit(root.id)

    @staticmethod
    def resolve_default_sales_organizations(root, info):
        return resolve_default_sales_organizations(root.id)

    @staticmethod
    def resolve_sales_org_by_bu_and_user(root, info):
        return resolve_scgp_sales_organizations_by_bu_and_user(root)

    @staticmethod
    def resolve_sales_org_by_bu(root, info):
        return resolve_scgp_sales_organizations_by_bu(root)


class ScgpUser(User):
    id = graphene.ID()
    sold_tos = graphene.List(SoldToMaster)
    permission_groups = graphene.List(ScgpGroup)
    extend_data = graphene.Field(ScgpUserExtend)

    class Meta:
        description = "ScgpUser extend data."
        model = UserModel

    @staticmethod
    def resolve_sold_tos(root, info):
        return resolve_sold_tos_by_user(root.id)

    @staticmethod
    def resolve_extend_data(root, info):
        return resolve_user_extend_data(root.id)


class ScgpUserCountableConnection(ScgCountableConnection):
    class Meta:
        node = ScgpUser


class GDCUserData(graphene.ObjectType):
    employee_id = graphene.String()
    email = graphene.String()
    first_name = graphene.String()
    last_name = graphene.String()
    sale_orgs = graphene.List(SalesOrganizationMaster)
    bus = graphene.List(BusinessUnits)

    class Meta:
        description = "GDC User Data."


class UserManagementSaleOrgCountTableConnection(CountableConnection):
    class Meta:
        node = SalesOrganizationMaster


class UserManagementSalesGroupCountTableConnection(CountableConnection):
    class Meta:
        node = SalesGroupMaster


class UserManagementSaleOfficeCountTableConnection(CountableConnection):
    class Meta:
        node = SalesOfficeMaster

class MenuFunction(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()

    class Meta:
        description = "ScgpUser extend data."
        model = MenuFunction

class ScgpGroupsAndMenuFunctions(Group):
    id = graphene.ID()
    menu_functions = graphene.List(MenuFunction)
    class Meta:
        description = "Scgp Group."
        model = GroupModel

    @staticmethod
    def resolve_menu_functions(root, info):
        return resolve_menu_function_by_group(root.id)


class ParentGroupAndRole(ModelObjectType):
    id = graphene.ID()
    name = graphene.String()
    code = graphene.String()
    groups = graphene.List(ScgpGroupsAndMenuFunctions, description="List of role group and its menu function ")
    description = graphene.String()

    class Meta:
        model = models.ParentGroup

    @staticmethod
    def resolve_groups(root, info):
        return resolve_groups_and_sort_by_index(root.id)


class ParentGroupRoleMenuCountableConnection(CountableConnection):
    class Meta:
        node = ParentGroupAndRole