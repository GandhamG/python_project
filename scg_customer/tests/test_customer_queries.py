from saleor.account.models import User
from saleor.graphql.tests.utils import (
    assert_graphql_error_with_message,
    get_graphql_content,
)
from scg_customer.tests.operations import CUSTOMER_QUERY


def test_customer_query(
    staff_api_client,
    scg_customers_account_address,
    scg_customers_for_search,
):
    variables = {"id": scg_customers_for_search[0].id}
    response = staff_api_client.post_graphql(
        CUSTOMER_QUERY,
        variables,
    )
    customer = User.objects.get(id=variables.get("id"))
    content = get_graphql_content(response)
    assert content["data"]["customer"].get("id") == str(customer.id)
    assert (
        len(content["data"]["customer"].get("addresses")) == customer.addresses.count()
    )


def test_customer_query_id_not_exist(
    staff_api_client,
    scg_customers_account_address,
    scg_customers_for_search,
):
    variables = {"id": 1000}
    response = staff_api_client.post_graphql(
        CUSTOMER_QUERY,
        variables,
    )
    content = get_graphql_content(response)
    assert content["data"]["customer"] == None


def test_customer_query_invalid_id_type(
    staff_api_client,
    scg_customers_account_address,
    scg_customers_for_search,
):
    variables = {"id": "abc"}
    response = staff_api_client.post_graphql(
        CUSTOMER_QUERY,
        variables,
    )
    message = "Field 'id' expected a number but got 'abc'."
    assert_graphql_error_with_message(response, message)
