import graphene
from saleor.graphql.core.connection import create_connection_slice, filter_connection_queryset
from saleor.graphql.core.fields import FilterConnectionField, PermissionsField
from sap_migration.graphql.types import SoldToMasterCountableConnection
from scgp_export.graphql.resolvers.connections import resolve_connection_slice
from scgp_user_management.graphql.filters import (
    ScgpUsersFilterInput,
    UserManagementSoldToFilterInput,
    UserManagementSaleOrgFilterInput,
    UserManagementSalesGroupFilterInput,
    UserManagementSaleOfficeFilterInput,
)

from scgp_user_management.graphql.mutations.scgp_users import (
    ScgpUserRegister,
    ScgpUserUpdate,
    ChangeScgpUserStatus,
    ScgpUserSendMailResetPassword,
    ScgpUserCheckValidTokenResetPassword,
    ScgpUserConfirmResetPassword,
    ScgpUserLogin,
    ScgpUserFirstLoginUpdate,
    ScgpUserMappingData,
    ScgpDeleteUser,
)
from scgp_user_management.graphql.resolvers.scgp_users import (
    resolve_parent_group,
    resolve_parent_groups,
    resolve_scgp_users,
    resolve_scgp_user,
    resolve_filter_sold_to_scg_checkout,
    resolve_scgp_me,
    resolve_scgp_gdc_data,
    resolve_filter_sale_organization,
    resolve_filter_sales_group,
    resolve_filter_sale_office,
)
from scgp_user_management.graphql.sorters import ScgpUserSortingInput
from scgp_user_management.graphql.types import (
    ParentGroupCountableConnection,
    ParentGroup,
    ScgpUserCountableConnection,
    ScgpUser,
    UserManagementSaleOrgCountTableConnection,
    UserManagementSalesGroupCountTableConnection,
    UserManagementSaleOfficeCountTableConnection, ParentGroupRoleMenuCountableConnection,
)


class ScgpUserManagementQueries(graphene.ObjectType):
    parent_group = PermissionsField(
        ParentGroup,
        description="Look up a parent group by ID",
        id=graphene.Argument(
            graphene.ID, description="ID of parent group", required=True
        ),
    )

    parent_groups = FilterConnectionField(
        ParentGroupCountableConnection,
        description="List of parent groups",
    )

    scgp_users = FilterConnectionField(
        ScgpUserCountableConnection,
        filter=ScgpUsersFilterInput(),
        sort_by=ScgpUserSortingInput(description="Sort scgp users."),
        description="List of scgp_user",
    )

    scgp_user = graphene.Field(
        ScgpUser,
        description="query 1 user detail",
        id=graphene.Argument(graphene.ID, description="ID of user", required=True)
    )

    filter_sold_to_scg_checkout = FilterConnectionField(
        SoldToMasterCountableConnection,
        filter=UserManagementSoldToFilterInput()
    )

    scgp_me = graphene.Field(ScgpUser)

    scgp_gdc_data = graphene.Field(
        "scgp_user_management.graphql.types.GDCUserData",
        ad_user=graphene.Argument(graphene.String, description="AD USER.", required=True),
    )
    filter_user_management_sale_org_by_bu = FilterConnectionField(
        UserManagementSaleOrgCountTableConnection,
        filter=UserManagementSaleOrgFilterInput()
    )

    filter_user_management_sale_group_by_sale_org = FilterConnectionField(
        UserManagementSalesGroupCountTableConnection,
        filter=UserManagementSalesGroupFilterInput()
    )

    filter_user_management_sale_office_by_sale_org = FilterConnectionField(
        UserManagementSaleOfficeCountTableConnection,
        filter=UserManagementSaleOfficeFilterInput()
    )

    get_roles_and_menu_functions = FilterConnectionField(
        ParentGroupRoleMenuCountableConnection,
        description="List of parent groups, roles and menu functions",
    )

    @staticmethod
    def resolve_filter_user_management_sale_org_by_bu(self, info, **kwargs):
        qs = resolve_filter_sale_organization()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, UserManagementSaleOrgCountTableConnection
        )

    @staticmethod
    def resolve_filter_user_management_sale_group_by_sale_org(self, info, **kwargs):
        qs = resolve_filter_sales_group()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, UserManagementSalesGroupCountTableConnection
        )

    @staticmethod
    def resolve_filter_user_management_sale_office_by_sale_org(self, info, **kwargs):
        qs = resolve_filter_sale_office()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, UserManagementSaleOfficeCountTableConnection
        )

    @staticmethod
    def resolve_scgp_user(self, info, **kwargs):
        pk = kwargs.get("id")
        return resolve_scgp_user(pk)

    @staticmethod
    def resolve_parent_group(self, info, **kwargs):
        pk = kwargs.get("id")
        return resolve_parent_group(pk)

    @staticmethod
    def resolve_parent_groups(self, info, **kwargs):
        qs = resolve_parent_groups()
        return create_connection_slice(
            qs, info, kwargs, ParentGroupCountableConnection
        )

    @staticmethod
    def resolve_scgp_users(self, info, **kwargs):
        qs = resolve_scgp_users()
        qs = filter_connection_queryset(qs, kwargs)
        return resolve_connection_slice(
            qs, info, kwargs, ScgpUserCountableConnection
        )

    @staticmethod
    def resolve_filter_sold_to_scg_checkout(self, info, **kwargs):
        qs = resolve_filter_sold_to_scg_checkout()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, SoldToMasterCountableConnection)

    @staticmethod
    def resolve_scgp_me(self, info, **kwargs):
        return resolve_scgp_me(info.context.user)

    @staticmethod
    def resolve_scgp_gdc_data(self, info, **kwargs):
        ad_user = kwargs.get("ad_user")
        return resolve_scgp_gdc_data(info, ad_user)

    @staticmethod
    def resolve_get_roles_and_menu_functions(self, info, **kwargs):
        qs = resolve_parent_groups()
        return create_connection_slice(
            qs, info, kwargs, ParentGroupRoleMenuCountableConnection
        )


class ScgpUserManagementMutations(graphene.ObjectType):
    scgp_user_register = ScgpUserRegister.Field()
    scgp_user_update = ScgpUserUpdate.Field()
    change_scgp_user_status = ChangeScgpUserStatus.Field()
    scgp_user_send_mail_reset_password = ScgpUserSendMailResetPassword.Field()
    scgp_user_check_valid_token_reset_password = ScgpUserCheckValidTokenResetPassword.Field()
    scgp_user_confirm_reset_password = ScgpUserConfirmResetPassword.Field()
    scgp_user_login = ScgpUserLogin.Field()
    scgp_user_first_login_update = ScgpUserFirstLoginUpdate.Field()
    scgp_user_mapping_data = ScgpUserMappingData.Field()
    scgp_delete_user = ScgpDeleteUser.Field()
