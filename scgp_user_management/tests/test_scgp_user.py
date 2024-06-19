import mock

# from saleor.account.models import Group, User
from saleor.graphql.tests.utils import (
    get_graphql_content,
)  # assert_graphql_error_with_message,

# from sap_migration.models import (
#     BusinessUnits,
#     DistributionChannelMaster,
#     DivisionMaster,
#     SalesGroupMaster,
#     SalesOfficeMaster,
#     SalesOrganizationMaster,
#     SoldToMaster,
# )
from scgp_user_management.graphql.validators import (
    check_email_exist,
    check_external_email,
    check_valid_email,
    check_valid_id,
    check_valid_password,
)
from scgp_user_management.models import ScgpUserTokenResetPassword  # , ScgpUser
from scgp_user_management.tests.operations import (  # SCGP_USER_CUSTOMER_REGISTER_MUTATION,; SCGP_USER_OTHER_REGISTER_MUTATION,; SCGP_USER_SALES_REGISTER_MUTATION,; SCGP_USER_UPDATE_MUTATION,
    SCGP_USER_CONFIRM_RESET_PASSWORD,
    SCGP_USER_SEND_MAIL_RESET_PASSWORD,
)

# @mock.patch("saleor.plugins.manager.PluginsManager.scgp_user_send_welcome_mail")
# @mock.patch("saleor.plugins.manager.PluginsManager.get_user_data_by_aduser")
# def test_create_user_sales(
#     get_gdc_data_mock,
#     send_mail_mock,
#     superuser_api_client,
#     user_parent_groups_data_test,
#     user_groups_data_test,
# ):
#     get_gdc_data_mock.return_value = {
#         "employeeId": 78982,
#         "empCode": None,
#         "organizationId": 79804,
#         "organizationName": "Application Maintenance Support",
#         "adAcount": "paper_temp5",
#         "t_FullName": "paper_temp5 paper_temp5",
#         "e_FullName": "paper_temp5 paper_temp5",
#         "nickName": None,
#         "positionName": None,
#         "businessUnit": "CCC",
#         "companyCode": "0740",
#         "companyName": "SCG Packaging Public Company Limited",
#         "div_Name": "Technology and Digital Platform",
#         "dep_Name": "Application Maintenance Support",
#         "subDep_Name": "",
#         "sec_Name": "Application Maintenance Support",
#         "email": "paper_temp5@scg.com",
#         "location": None,
#         "employeeOrganizationRelationTypeId": 1,
#         "empOrgLevel": 900,
#         "cctR_Dept": "0740-22400",
#         "cctR_Over": None,
#         "managerEmail": None,
#         "tel": None,
#         "mobileNo": None,
#     }
#     variables = {
#         "input": {
#             "userParentGroupId": user_parent_groups_data_test[0].id,
#             "email": "",
#             "firstName": "",
#             "lastName": "",
#             "groupIds": [user_groups_data_test[0].id, user_groups_data_test[1].id],
#             "adUser": "paper_temp5",
#             "saleId": "111",
#             "employeeId": "",
#         }
#     }
#     response = superuser_api_client.post_graphql(
#         SCGP_USER_SALES_REGISTER_MUTATION,
#         variables=variables,
#     )
#     content = get_graphql_content(response)
#     created_user = User.objects.filter(email="paper_temp5@scg.com").first()
#     extend_data = ScgpUser.objects.filter(user_id=created_user.id).first()

#     assert [
#         x["name"]
#         for x in content["data"]["scgpUserRegister"]["user"]["permissionGroups"]
#     ] == list(
#         Group.objects.filter(user__id=created_user.id).values_list("name", flat=True)
#     )
#     assert content["data"]["scgpUserRegister"]["user"]["email"] == created_user.email
#     assert (
#         content["data"]["scgpUserRegister"]["user"]["extendData"]["adUser"]
#         == extend_data.ad_user
#     )


# @mock.patch("saleor.plugins.manager.PluginsManager.scgp_user_send_welcome_mail")
# def test_create_user_customer(
#     send_mail_mock,
#     superuser_api_client,
#     user_parent_groups_data_test,
#     user_groups_data_test,
#     scg_sold_tos_data_test,
#     scg_sold_to_externals_data_test,
# ):
#     variables = {
#         "input": {
#             "userParentGroupId": user_parent_groups_data_test[1].id,
#             "email": "test38@gmail.com",
#             "firstName": "Thang",
#             "lastName": "Nguyen",
#             "groupIds": [user_groups_data_test[1].id],
#             "customerType": "INTERNAL",
#             "companyEmail": "test@gmail.com",
#             "displayName": "tessss",
#             "soldToIds": [scg_sold_tos_data_test[0].id, scg_sold_tos_data_test[1].id],
#         }
#     }
#     response = superuser_api_client.post_graphql(
#         SCGP_USER_CUSTOMER_REGISTER_MUTATION,
#         variables=variables,
#     )
#     content = get_graphql_content(response)
#     created_user = User.objects.filter(email="test38@gmail.com").first()
#     extend_data = ScgpUser.objects.filter(user_id=created_user.id).first()

#     assert [
#         x["name"]
#         for x in content["data"]["scgpUserRegister"]["user"]["permissionGroups"]
#     ] == list(
#         Group.objects.filter(user__id=created_user.id).values_list("name", flat=True)
#     )
#     assert content["data"]["scgpUserRegister"]["user"]["email"] == created_user.email
#     assert [
#         x["code"] for x in content["data"]["scgpUserRegister"]["user"]["soldTos"]
#     ] == list(
#         SoldToMaster.objects.filter(user__id=created_user.id).values_list(
#             "sold_to_code", flat=True
#         )
#     )
#     assert (
#         content["data"]["scgpUserRegister"]["user"]["extendData"]["displayName"]
#         == extend_data.display_name
#     )
#     assert (
#         content["data"]["scgpUserRegister"]["user"]["extendData"]["customerType"]
#         == extend_data.customer_type
#     )


# @mock.patch("saleor.plugins.manager.PluginsManager.scgp_user_send_welcome_mail")
# @mock.patch("saleor.plugins.manager.PluginsManager.get_user_data_by_aduser")
# def test_create_user_other(
#     get_gdc_data_mock,
#     send_mail_mock,
#     superuser_api_client,
#     user_parent_groups_data_test,
#     user_groups_data_test,
#     scgp_bus_data_test,
#     scgp_sales_organizations_data_test,
#     scgp_sales_groups_data_test,
#     scgp_distribution_channels_data_test,
#     scgp_divisions_data_test,
#     scgp_sales_offices_data_test,
# ):
#     get_gdc_data_mock.return_value = {
#         "employeeId": 78982,
#         "empCode": None,
#         "organizationId": 79804,
#         "organizationName": "Application Maintenance Support",
#         "adAcount": "paper_temp5",
#         "t_FullName": "paper_temp5 paper_temp5",
#         "e_FullName": "paper_temp5 paper_temp5",
#         "nickName": None,
#         "positionName": None,
#         "businessUnit": "CCC",
#         "companyCode": "0740",
#         "companyName": "SCG Packaging Public Company Limited",
#         "div_Name": "Technology and Digital Platform",
#         "dep_Name": "Application Maintenance Support",
#         "subDep_Name": "",
#         "sec_Name": "Application Maintenance Support",
#         "email": "paper_temp5@scg.com",
#         "location": None,
#         "employeeOrganizationRelationTypeId": 1,
#         "empOrgLevel": 900,
#         "cctR_Dept": "0740-22400",
#         "cctR_Over": None,
#         "managerEmail": None,
#         "tel": None,
#         "mobileNo": None,
#     }
#     variables = {
#         "input": {
#             "userParentGroupId": user_parent_groups_data_test[2].id,
#             "email": "",
#             "firstName": "",
#             "lastName": "",
#             "groupIds": [user_groups_data_test[2].id],
#             "adUser": "paper_temp5",
#             "employeeId": "",
#             "scgpBuIds": [scgp_bus_data_test[0].id],
#             "scgpSalesOrganizationIds": [],
#             "scgpSalesGroupIds": [scgp_sales_groups_data_test[0].id],
#             "scgpDistributionChannelIds": [scgp_distribution_channels_data_test[0].id],
#             "scgpDivisionIds": [scgp_divisions_data_test[0].id],
#             "scgpSalesOfficeIds": [scgp_sales_offices_data_test[0].id],
#         }
#     }
#     response = superuser_api_client.post_graphql(
#         SCGP_USER_OTHER_REGISTER_MUTATION,
#         variables=variables,
#     )
#     content = get_graphql_content(response)
#     created_user = User.objects.filter(email="paper_temp5@scg.com").first()
#     extend_data = ScgpUser.objects.filter(user_id=created_user.id).first()

#     assert [
#         x["name"]
#         for x in content["data"]["scgpUserRegister"]["user"]["permissionGroups"]
#     ] == list(
#         Group.objects.filter(user__id=created_user.id).values_list("name", flat=True)
#     )
#     assert content["data"]["scgpUserRegister"]["user"]["email"] == created_user.email

#     assert [
#         x["name"]
#         for x in content["data"]["scgpUserRegister"]["user"]["extendData"]["scgpBus"]
#     ] == list(
#         BusinessUnits.objects.filter(scgpuser__id=extend_data.id).values_list(
#             "name", flat=True
#         )
#     )
#     assert [
#         x["name"]
#         for x in content["data"]["scgpUserRegister"]["user"]["extendData"][
#             "scgpDistributionChannels"
#         ]
#     ] == list(
#         DistributionChannelMaster.objects.filter(
#             scgpuser__id=extend_data.id
#         ).values_list("name", flat=True)
#     )
#     assert [
#         x["name"]
#         for x in content["data"]["scgpUserRegister"]["user"]["extendData"][
#             "scgpDivisions"
#         ]
#     ] == list(
#         DivisionMaster.objects.filter(scgpuser__id=extend_data.id).values_list(
#             "name", flat=True
#         )
#     )
#     assert [
#         x["name"]
#         for x in content["data"]["scgpUserRegister"]["user"]["extendData"][
#             "scgpSalesGroups"
#         ]
#     ] == list(
#         SalesGroupMaster.objects.filter(scgpuser__id=extend_data.id).values_list(
#             "name", flat=True
#         )
#     )
#     assert [
#         x["name"]
#         for x in content["data"]["scgpUserRegister"]["user"]["extendData"][
#             "scgpSalesOffices"
#         ]
#     ] == list(
#         SalesOfficeMaster.objects.filter(scgpuser__id=extend_data.id).values_list(
#             "name", flat=True
#         )
#     )
#     assert [
#         x["name"]
#         for x in content["data"]["scgpUserRegister"]["user"]["extendData"][
#             "scgpSalesOrganizations"
#         ]
#     ] == list(
#         SalesOrganizationMaster.objects.filter(scgpuser__id=extend_data.id).values_list(
#             "name", flat=True
#         )
#     )


# def test_create_user_missing_require_fields(
#     superuser_api_client,
#     user_parent_groups_data_test,
#     user_groups_data_test,
# ):
#     variables = {
#         "input": {
#             "userParentGroupId": user_parent_groups_data_test[0].id,
#             "email": "",
#             "firstName": "",
#             "lastName": "",
#             "groupIds": [user_groups_data_test[0].id, user_groups_data_test[1].id],
#         }
#     }
#     response = superuser_api_client.post_graphql(
#         SCGP_USER_SALES_REGISTER_MUTATION,
#         variables=variables,
#     )
#     assert_graphql_error_with_message(response, "'ad_user'")


# def test_update_user(
#     scgp_users_test,
#     superuser_api_client,
#     user_parent_groups_data_test,
#     user_groups_data_test,
#     scg_sold_tos_data_test,
# ):
#     variables = {
#         "id": scgp_users_test[1].id,
#         "input": {
#             "userParentGroupId": user_parent_groups_data_test[1].id,
#             "email": "huhu@gmail.com",
#             "firstName": "Thang",
#             "lastName": "Nguyen",
#             "groupIds": [user_groups_data_test[1].id],
#             "customerType": "EXTERNAL",
#             "companyEmail": "test@gmail.com",
#             "displayName": "tss",
#             "soldToIds": [scg_sold_tos_data_test[1].id, scg_sold_tos_data_test[2].id],
#             "isActive": True,
#         },
#     }
#     response = superuser_api_client.post_graphql(
#         SCGP_USER_UPDATE_MUTATION,
#         variables=variables,
#     )
#     content = get_graphql_content(response)
#     created_user = User.objects.filter(email="huhu@gmail.com").first()
#     extend_data = ScgpUser.objects.filter(user_id=created_user.id).first()

#     assert [
#         x["name"] for x in content["data"]["scgpUserUpdate"]["user"]["permissionGroups"]
#     ] == list(
#         Group.objects.filter(user__id=created_user.id).values_list("name", flat=True)
#     )
#     assert content["data"]["scgpUserUpdate"]["user"]["email"] == created_user.email
#     assert [
#         x["code"] for x in content["data"]["scgpUserUpdate"]["user"]["soldTos"]
#     ] == list(
#         SoldToMaster.objects.filter(user__id=created_user.id).values_list(
#             "sold_to_code", flat=True
#         )
#     )
#     assert (
#         content["data"]["scgpUserUpdate"]["user"]["extendData"]["displayName"]
#         == extend_data.display_name
#     )
#     assert (
#         content["data"]["scgpUserUpdate"]["user"]["extendData"]["customerType"]
#         == extend_data.customer_type
#     )


def test_validator(user_datas_test):
    assert not check_valid_email("a")
    assert check_valid_email("test@gmail.com")

    assert not check_email_exist("test1@gmail.com")
    assert check_email_exist("aaaaa@gmail.com")

    assert not check_external_email("test1@scg.com")
    assert check_external_email("aaaaa@gmail.com")

    assert not check_valid_id("xxxxx")
    assert check_valid_id("11111")

    assert check_valid_password("ABCa123aaaa")


@mock.patch(
    "saleor.plugins.manager.PluginsManager.scgp_user_check_valid_token_reset_password"
)
def test_change_password_user(user_send_mail_mock, api_client, user_datas_test):
    variables = {"email": user_datas_test[0].email}
    response = api_client.post_graphql(
        SCGP_USER_SEND_MAIL_RESET_PASSWORD,
        variables=variables,
    )
    content = get_graphql_content(response)
    user_token = ScgpUserTokenResetPassword.objects.filter(
        user=user_datas_test[0]
    ).first()
    assert len(content["data"]["scgpUserSendMailResetPassword"]["errors"]) == 0

    variables1 = {
        "email": user_datas_test[0].email,
        "token": user_token.token,
        "new_password": "1234ABC33a",
        "confirm_password": "1234ABC33a",
    }
    response1 = api_client.post_graphql(
        SCGP_USER_CONFIRM_RESET_PASSWORD,
        variables=variables1,
    )
    content1 = get_graphql_content(response1)
    assert len(content1["data"]["scgpUserConfirmResetPassword"]["errors"]) == 0
