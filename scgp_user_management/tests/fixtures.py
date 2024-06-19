import pytest

from saleor.account.models import Group, User
from sap_master_data.models import SoldToExternalMaster
from sap_migration.models import (
    BusinessUnits,
    DistributionChannelMaster,
    DivisionMaster,
    SalesGroupMaster,
    SalesOfficeMaster,
    SalesOrganizationMaster,
    SoldToMaster,
)
from scgp_user_management.models import (
    EmailConfigurationExternal,
    EmailConfigurationInternal,
    EmailInternalMapping,
    ParentGroup,
    ScgpUser,
)


@pytest.fixture
def scg_sold_tos_data_test(db):
    return SoldToMaster.objects.bulk_create(
        [
            SoldToMaster(
                sold_to_code="sold_to_1",
            ),
            SoldToMaster(
                sold_to_code="sold_to_2",
            ),
            SoldToMaster(
                sold_to_code="sold_to_3",
            ),
        ]
    )


@pytest.fixture
def scg_sold_to_externals_data_test(scg_sold_tos_data_test):
    return SoldToExternalMaster.objects.bulk_create(
        [
            SoldToExternalMaster(
                sold_to_code="sold_to_1",
                sold_to_name="sold name 1",
                sold_to=scg_sold_tos_data_test[0],
            ),
            SoldToExternalMaster(
                sold_to_code="sold_to_2",
                sold_to_name="sold name 2",
                sold_to=scg_sold_tos_data_test[1],
            ),
            SoldToExternalMaster(
                sold_to_code="sold_to_3",
                sold_to_name="sold name 3",
                sold_to=scg_sold_tos_data_test[2],
            ),
        ]
    )


@pytest.fixture
def scgp_bus_data_test(db):
    return BusinessUnits.objects.bulk_create(
        [
            BusinessUnits(code="PP", name="PP"),
            BusinessUnits(code="FB", name="FB"),
            BusinessUnits(code="CIP", name="CIP"),
        ]
    )


@pytest.fixture
def scgp_sales_organizations_data_test(db):
    return SalesOrganizationMaster.objects.bulk_create(
        [
            SalesOrganizationMaster(name="1", code="1"),
            SalesOrganizationMaster(name="2", code="2"),
            SalesOrganizationMaster(name="3", code="3"),
        ]
    )


@pytest.fixture
def scgp_sales_groups_data_test(db):
    return SalesGroupMaster.objects.bulk_create(
        [
            SalesGroupMaster(name="1", code="1"),
            SalesGroupMaster(name="2", code="2"),
            SalesGroupMaster(name="3", code="3"),
        ]
    )


@pytest.fixture
def scgp_distribution_channels_data_test(db):
    return DistributionChannelMaster.objects.bulk_create(
        [
            DistributionChannelMaster(name="1", code="1"),
            DistributionChannelMaster(name="2", code="2"),
            DistributionChannelMaster(name="3", code="3"),
        ]
    )


@pytest.fixture
def scgp_divisions_data_test(db):
    return DivisionMaster.objects.bulk_create(
        [
            DivisionMaster(name="1", code="1"),
            DivisionMaster(name="2", code="2"),
            DivisionMaster(name="3", code="3"),
        ]
    )


@pytest.fixture
def scgp_sales_offices_data_test(db):
    return SalesOfficeMaster.objects.bulk_create(
        [
            SalesOfficeMaster(name="1", code="1"),
            SalesOfficeMaster(name="2", code="2"),
            SalesOfficeMaster(name="3", code="3"),
        ]
    )


@pytest.fixture
def user_groups_data_test(db):
    return Group.objects.bulk_create(
        [
            Group(name="1"),
            Group(name="2"),
            Group(name="3"),
        ]
    )


@pytest.fixture
def user_parent_groups_data_test(user_groups_data_test):
    parent_group_1 = ParentGroup.objects.create(name="Sales")
    parent_group_1.groups.set(
        [user_groups_data_test[0].id, user_groups_data_test[1].id]
    )

    parent_group_2 = ParentGroup.objects.create(name="Customer")
    parent_group_2.groups.set([user_groups_data_test[1].id])

    parent_group_3 = ParentGroup.objects.create(name="Other")
    parent_group_3.groups.set([user_groups_data_test[2].id])

    return [
        parent_group_1,
        parent_group_2,
        parent_group_3,
    ]


@pytest.fixture
def user_datas_test(user_groups_data_test):
    user_1 = User.objects.create(
        email="test1@gmail.com",
        first_name="test",
        last_name="1",
        is_active=True,
    )
    user_1.groups.set([user_groups_data_test[0].id, user_groups_data_test[1].id])

    user_2 = User.objects.create(
        email="test2@gmail.com",
        first_name="test",
        last_name="2",
        is_active=True,
    )
    user_2.groups.set([user_groups_data_test[1].id])

    user_3 = User.objects.create(
        email="test3mail.com",
        first_name="test",
        last_name="3",
        is_active=True,
    )
    user_3.groups.set([user_groups_data_test[2].id])

    return [user_1, user_2, user_3]


@pytest.fixture
def scgp_users_test(
    user_datas_test,
    scg_sold_tos_data_test,
    scgp_bus_data_test,
    scgp_sales_organizations_data_test,
    scgp_sales_groups_data_test,
    scgp_distribution_channels_data_test,
    scgp_divisions_data_test,
    scgp_sales_offices_data_test,
    user_parent_groups_data_test,
):
    scgp_user_1 = ScgpUser.objects.create(
        user_parent_group_id=user_parent_groups_data_test[0].id,
        user=user_datas_test[0],
        ad_user="aduser 1",
        employee_id="1111",
        sale_id="1111",
    )

    scgp_user_2 = ScgpUser.objects.create(
        user_parent_group_id=user_parent_groups_data_test[1].id,
        user=user_datas_test[1],
        customer_type="INTERNAL",
        company_email="company@gmail.com",
        display_name="User 2",
    )
    user_datas_test[1].master_sold_to.set(
        [scg_sold_tos_data_test[0].id, scg_sold_tos_data_test[1].id]
    )

    scgp_user_3 = ScgpUser.objects.create(
        user_parent_group_id=user_parent_groups_data_test[2].id,
        user=user_datas_test[2],
        ad_user="aduser 3",
        employee_id="2222",
        display_name="User 2",
    )
    scgp_user_3.scgp_bus.set([scgp_bus_data_test[1].id])
    scgp_user_3.scgp_sales_organizations.set([scgp_sales_organizations_data_test[1].id])
    scgp_user_3.scgp_sales_groups.set([scgp_sales_groups_data_test[1].id])
    scgp_user_3.scgp_distribution_channels.set(
        [scgp_distribution_channels_data_test[1].id]
    )
    scgp_user_3.scgp_divisions.set([scgp_divisions_data_test[1].id])
    scgp_user_3.scgp_sales_offices.set([scgp_sales_offices_data_test[1].id])

    return [scgp_user_1, scgp_user_2, scgp_user_3]


@pytest.fixture
def scgp_users_email_internal_mapping(scgp_user_email_configuration_internal):
    email_internal_mappings = [
        # all product groups & all sale org case
        EmailInternalMapping(
            bu="bu1",
            sale_org="All",
            team="team1",
            product_group="All",
            email="mailto1@example",
        ),
        # all product groups & all sale org case : Case in-sensitive
        EmailInternalMapping(
            bu="bu7",
            sale_org="All",
            team="team7",
            product_group="ALL",
            email="mailto7@example",
        ),
        # Sale Org Defined & product group Undefined
        EmailInternalMapping(
            bu="bu2",
            sale_org="0004",
            team="team2",
            product_group="0000",
            email="mailto2@example",
        ),
        # Sale Org Undefined and product group Defined
        EmailInternalMapping(
            bu="bu8",
            sale_org="0000",
            team="team8",
            product_group="All",
            email="mailto8@example",
        ),
        # Both Sale Org and product group Undefined
        EmailInternalMapping(
            bu="bu3",
            sale_org="0000",
            team="team3",
            product_group="0000",
            email="mailto3@example",
        ),
        # normal case
        EmailInternalMapping(
            bu="bu4",
            sale_org="0001",
            team="team4",
            product_group="p01",
            email="mailto4@example",
        ),
        # multiple email case
        EmailInternalMapping(
            bu="bu5",
            sale_org="0002",
            team="team5",
            product_group="p02",
            email="mailto5.1@example, mailto5.2@example",
        ),
        # default BU and covering specific and all cases when sale org & product group defined
        EmailInternalMapping(
            bu="pp",
            sale_org="0001",
            team="team9",
            product_group="p02",
            email="mailto9@example",
        ),
        EmailInternalMapping(
            bu="pp",
            sale_org="All",
            team="team9",
            product_group="ALL",
            email="mailto9@example,mailto10@example",
        ),
        EmailInternalMapping(
            bu="pp",
            sale_org="All",
            team="team9",
            product_group="p02",
            email="mailto11@example",
        ),
        EmailInternalMapping(
            bu="pp",
            sale_org="0001",
            team="team9",
            product_group="All",
            email="mailto12@example",
        ),
        # empty email case
        EmailInternalMapping(
            bu="bu3",
            sale_org="0003",
            team="team3",
            product_group="p03",
            email="",
        ),
    ]
    return EmailInternalMapping.objects.bulk_create(email_internal_mappings)


@pytest.fixture
def scgp_user_email_configuration_internal():
    email_configs = [
        EmailConfigurationInternal(bu="bu1", team="team1", create_order=True),
        EmailConfigurationInternal(bu="bu2", team="team2", po_upload=True),
        EmailConfigurationInternal(bu="bu3", team="team3", order_confirmation=True),
        EmailConfigurationInternal(bu="bu4", team="team4", pending_order=True),
        EmailConfigurationInternal(bu="bu5", team="team5", eo_upload=True),
        EmailConfigurationInternal(bu="bu6", team="team6", require_attention=True),
        EmailConfigurationInternal(bu="bu7", team="team7", create_order=True),
        EmailConfigurationInternal(bu="bu8", team="team8", create_order=True),
        EmailConfigurationInternal(bu="pp", team="team9", eo_upload=True),
    ]
    return EmailConfigurationInternal.objects.bulk_create(email_configs)


@pytest.fixture
def scgp_user_email_configuration_external(db):
    EmailConfigurationExternal.objects.create(
        product_group="GroupA",
        sold_to_code="001",
        feature="FeatureA",
        mail_to="mailtoA1@example.com,mailtoA2@example.com",
        cc_to="cctoA1@example.com",
    )
    EmailConfigurationExternal.objects.create(
        product_group="GroupB",
        sold_to_code="002",
        feature="FeatureB",
        mail_to="mailtoB1@example.com",
        cc_to="cctoB1@example.com,cctoB2@example.com",
    )
    EmailConfigurationExternal.objects.create(
        product_group="All",
        sold_to_code="003",
        feature="FeatureC",
        mail_to="",
        cc_to="cctoC1@example.com,cctoC2@example.com",
    )
    EmailConfigurationExternal.objects.create(
        product_group="GroupD",
        sold_to_code="004",
        feature="FeatureD",
        mail_to="mailtoD1@example.com",
        cc_to="",
    )
    EmailConfigurationExternal.objects.create(
        product_group=" ",
        sold_to_code="0005",
        feature="FeatureE",
        mail_to="mailtoE1@example.com",
        cc_to="cctoE1@example.com",
    )
    EmailConfigurationExternal.objects.create(
        product_group='""',
        sold_to_code="0006",
        feature="FeatureF",
        mail_to="mailtoF1@example.com",
        cc_to="cctoF1@example.com",
    )
    EmailConfigurationExternal.objects.create(
        product_group="GroupG",
        sold_to_code="0007",
        feature="FeatureG",
        mail_to="",
        cc_to="",
    )
