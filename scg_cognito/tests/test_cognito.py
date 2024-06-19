from unittest.mock import patch

from django.utils import timezone
from freezegun import freeze_time
from pytz import UTC

from saleor.account.models import User
from saleor.graphql.tests.utils import get_graphql_content
from saleor.plugins.cognito_connect.plugin import ExternalCognitoUser
from scg_cognito.tests.operations import GENERATE_TOKEN_MUTATION


@patch("scg_cognito.graphql.mutations._get_new_csrf_token")
@patch("scg_cognito.graphql.mutations.create_access_token")
@patch("scg_cognito.graphql.mutations.create_refresh_token")
@patch("saleor.plugins.manager.PluginsManager.extenal_access_cognito")
def test_login_cognito_success_with_email_for_existing_user(
    mocked_access_cognito,
    mocked_refresh_token,
    mocked_access_token,
    mocked_csrf_token,
    api_client,
    customers_for_search,
):
    login_email = customers_for_search[0].email
    mocked_access_cognito.return_value = ExternalCognitoUser(email=login_email)

    request_time = timezone.datetime(2021, 1, 1, 12, 10, 5, tzinfo=UTC)
    authentication_info = mock_token_and_assert_response(
        mocked_refresh_token,
        mocked_access_token,
        mocked_csrf_token,
        api_client,
        request_time,
    )

    user_email = authentication_info["user"]["email"]
    user = User.objects.get(email=user_email)
    assert user.email == login_email
    assert user.last_login == request_time
    assert user.is_staff == customers_for_search[0].is_staff
    assert user.first_name == customers_for_search[0].first_name

    assert_mocked_call_count(
        1,
        mocked_access_cognito,
        mocked_refresh_token,
        mocked_access_token,
        mocked_csrf_token,
    )


@patch("scg_cognito.graphql.mutations._get_new_csrf_token")
@patch("scg_cognito.graphql.mutations.create_access_token")
@patch("scg_cognito.graphql.mutations.create_refresh_token")
@patch("saleor.plugins.manager.PluginsManager.extenal_access_cognito")
def test_login_cognito_success_with_username_for_existing_user(
    mocked_access_cognito,
    mocked_refresh_token,
    mocked_access_token,
    mocked_csrf_token,
    api_client,
    customers_for_search,
):
    login_username = customers_for_search[0].email
    mocked_access_cognito.return_value = ExternalCognitoUser(username=login_username)

    request_time = timezone.datetime(2021, 1, 1, 12, 10, 5, tzinfo=UTC)
    authentication_info = mock_token_and_assert_response(
        mocked_refresh_token,
        mocked_access_token,
        mocked_csrf_token,
        api_client,
        request_time,
    )

    user_email = authentication_info["user"]["email"]
    user = User.objects.get(email=user_email)
    assert user.email == login_username
    assert user.last_login == request_time
    assert user.is_staff == customers_for_search[0].is_staff
    assert user.first_name == customers_for_search[0].first_name


# @patch("scg_cognito.graphql.mutations._get_new_csrf_token")
# @patch("scg_cognito.graphql.mutations.create_access_token")
# @patch("scg_cognito.graphql.mutations.create_refresh_token")
# @patch("saleor.plugins.manager.PluginsManager.extenal_access_cognito")
# def test_login_cognito_success_with_email_for_new_user(
#     mocked_access_cognito,
#     mocked_refresh_token,
#     mocked_access_token,
#     mocked_csrf_token,
#     api_client,
# ):
#     login_email = "test@example.com"
#     mocked_access_cognito.return_value = ExternalCognitoUser(email=login_email)

#     request_time = timezone.datetime(2021, 1, 1, 12, 10, 5, tzinfo=UTC)
#     authentication_info = mock_token_and_assert_response(
#         mocked_refresh_token,
#         mocked_access_token,
#         mocked_csrf_token,
#         api_client,
#         request_time,
#     )

#     user_email = authentication_info["user"]["email"]
#     user = User.objects.get(email=user_email)
#     assert user.email == login_email
#     assert user.last_login == request_time
#     assert user.is_staff is False

#     assert_mocked_call_count(
#         1,
#         mocked_access_cognito,
#         mocked_refresh_token,
#         mocked_access_token,
#         mocked_csrf_token,
#     )


# @patch("scg_cognito.graphql.mutations._get_new_csrf_token")
# @patch("scg_cognito.graphql.mutations.create_access_token")
# @patch("scg_cognito.graphql.mutations.create_refresh_token")
# @patch("saleor.plugins.manager.PluginsManager.extenal_access_cognito")
# def test_login_cognito_success_with_username_for_new_user(
#     mocked_access_cognito,
#     mocked_refresh_token,
#     mocked_access_token,
#     mocked_csrf_token,
#     api_client,
# ):
#     login_username = "test_username"
#     mocked_access_cognito.return_value = ExternalCognitoUser(username=login_username)

#     request_time = timezone.datetime(2021, 1, 1, 12, 10, 5, tzinfo=UTC)
#     authentication_info = mock_token_and_assert_response(
#         mocked_refresh_token,
#         mocked_access_token,
#         mocked_csrf_token,
#         api_client,
#         request_time,
#     )

#     assert authentication_info["token"] == "access_token"
#     assert authentication_info["refreshToken"] == "refresh_token"
#     assert authentication_info["csrfToken"] == "csrf_token"
#     assert len(authentication_info["errors"]) == 0

#     user_email = authentication_info["user"]["email"]
#     user = User.objects.get(email=user_email)
#     assert user.email == login_username
#     assert user.last_login == request_time
#     assert user.is_staff is False

#     assert_mocked_call_count(
#         1,
#         mocked_access_cognito,
#         mocked_refresh_token,
#         mocked_access_token,
#         mocked_csrf_token,
#     )


def mock_token_and_assert_response(
    mocked_refresh_token,
    mocked_access_token,
    mocked_csrf_token,
    api_client,
    request_time,
):
    mocked_refresh_token.return_value = "refresh_token"
    mocked_access_token.return_value = "access_token"
    mocked_csrf_token.return_value = "csrf_token"

    variables = {"idToken": ""}
    with freeze_time(request_time):
        response = api_client.post_graphql(
            GENERATE_TOKEN_MUTATION,
            variables,
        )

    content = get_graphql_content(response)
    authentication_info = content["data"]["generateToken"]

    assert authentication_info["token"] == "access_token"
    assert authentication_info["refreshToken"] == "refresh_token"
    assert authentication_info["csrfToken"] == "csrf_token"
    assert len(authentication_info["errors"]) == 0

    return authentication_info


def assert_mocked_call_count(count, *mocked_functions):
    for mocked_function in mocked_functions:
        assert mocked_function.call_count == count


def test_login_cognito_error_invalid_token(api_client, customers_for_search):
    variables = {"idToken": ""}
    response = api_client.post_graphql(
        GENERATE_TOKEN_MUTATION,
        variables,
    )

    content = get_graphql_content(response)
    authentication_info = content["data"]["generateToken"]

    assert authentication_info["token"] is None
    assert authentication_info["refreshToken"] is None
    assert authentication_info["csrfToken"] is None
    assert authentication_info["user"] is None
    assert authentication_info["errors"][0]["code"] == "INVALID_CREDENTIALS"
