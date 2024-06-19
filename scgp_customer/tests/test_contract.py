from saleor.graphql.tests.utils import (
    get_graphql_content_from_response,
)  # get_graphql_content,

# from scgp_customer.models import CustomerContractProduct
from scgp_customer.tests.operations import (
    CUSTOMER_CONTRACT_QUERY,
)  # CUSTOMER_CONTRACT_NO_SORT_QUERY,

# def test_customer_contract_remain_desc_success(
#     staff_api_client,
#     scgp_customer_contracts,
#     scgp_customer_contract_product,
#     companies_for_search,
# ):
#     variables = {
#         "id": scgp_customer_contracts[2].id,
#         "productSort": {"direction": "DESC", "field": "REMAIN"},
#     }
#     response = staff_api_client.post_graphql(
#         CUSTOMER_CONTRACT_QUERY,
#         variables,
#     )

#     content = get_graphql_content(response)
#     customer_checkout_contract = content["data"]["customerContractDetail"]
#     company = customer_checkout_contract["company"]
#     products = customer_checkout_contract["products"]
#     assert (
#         company["businessUnit"]["name"]
#         == scgp_customer_contracts[2].company.business_unit.name
#     )
#     assert (
#         customer_checkout_contract["projectName"]
#         == scgp_customer_contracts[2].project_name
#     )
#     assert products[0]["remainingQuantity"] >= products[1]["remainingQuantity"]


# def test_customer_contract_remain_asc_success(
#     staff_api_client,
#     scgp_customer_contracts,
#     scgp_customer_contract_product,
#     companies_for_search,
# ):
#     variables = {
#         "id": scgp_customer_contracts[2].id,
#         "productSort": {"direction": "ASC", "field": "REMAIN"},
#     }
#     response = staff_api_client.post_graphql(
#         CUSTOMER_CONTRACT_QUERY,
#         variables,
#     )

#     content = get_graphql_content(response)
#     customer_checkout_contract = content["data"]["customerContractDetail"]
#     company = customer_checkout_contract["company"]
#     products = customer_checkout_contract["products"]
#     assert (
#         company["businessUnit"]["name"]
#         == scgp_customer_contracts[2].company.business_unit.name
#     )
#     assert (
#         customer_checkout_contract["projectName"]
#         == scgp_customer_contracts[2].project_name
#     )
#     assert products[0]["remainingQuantity"] <= products[1]["remainingQuantity"]


# def test_customer_contract_success_with_no_sort_by(
#     staff_api_client,
#     scgp_customer_contracts,
#     scgp_customer_contract_product,
#     companies_for_search,
# ):
#     variables = {
#         "id": scgp_customer_contracts[2].id,
#     }
#     response = staff_api_client.post_graphql(
#         CUSTOMER_CONTRACT_NO_SORT_QUERY,
#         variables,
#     )

#     content = get_graphql_content(response)
#     customer_checkout_contract = content["data"]["customerContractDetail"]
#     company = customer_checkout_contract["company"]
#     products = customer_checkout_contract["products"]
#     assert (
#         company["businessUnit"]["name"]
#         == scgp_customer_contracts[2].company.business_unit.name
#     )
#     assert (
#         customer_checkout_contract["projectName"]
#         == scgp_customer_contracts[2].project_name
#     )
#     assert (
#         len(products)
#         == CustomerContractProduct.objects.filter(
#             contract__id=scgp_customer_contracts[2].id
#         ).count()
#     )


# def test_customer_contract_query_anonymous_fail(
#     api_client,
#     scgp_customer_contracts,
#     scgp_customer_contract_product,
#     companies_for_search,
# ):
#     variables = {
#         "id": scgp_customer_contracts[2].id,
#         "productSort": {"direction": "DESC", "field": "REMAIN"},
#     }
#     response = api_client.post_graphql(
#         CUSTOMER_CONTRACT_QUERY,
#         variables,
#     )
#     content = get_graphql_content_from_response(response)

#     message = "You have to login!"
#     assert message == content["errors"][0]["message"]


def test_customer_contract_missing_foreign_key_success(
    staff_api_client,
    scgp_customer_contracts,
    scgp_customer_contract_product,
    companies_for_search,
):
    variables = {
        "id": "",
        "productSort": {"direction": "DESC", "field": "REMAIN"},
    }

    response = staff_api_client.post_graphql(
        CUSTOMER_CONTRACT_QUERY,
        variables,
    )
    content = get_graphql_content_from_response(response)
    message = "Field 'id' expected a number but got ''."
    assert message == content["errors"][0]["message"]


def test_customer_contract_wrong_type_success(
    staff_api_client,
    scgp_customer_contracts,
    scgp_customer_contract_product,
    companies_for_search,
):
    variables = {
        "id": "abc",
        "productSort": {"direction": "DESC", "field": "REMAIN"},
    }

    response = staff_api_client.post_graphql(
        CUSTOMER_CONTRACT_QUERY,
        variables,
    )
    content = get_graphql_content_from_response(response)
    message = "Field 'id' expected a number but got 'abc'."
    assert message == content["errors"][0]["message"]


# def test_customer_contract_success_customer_id(
#     staff_api_client,
#     scgp_customer_contracts,
#     scgp_customer_contract_product,
#     companies_for_search,
# ):
#     variables = {
#         "id": scgp_customer_contracts[2].id,
#     }
#     response = staff_api_client.post_graphql(
#         CUSTOMER_CONTRACT_NO_SORT_QUERY,
#         variables,
#     )

#     content = get_graphql_content(response)
#     customer_checkout_contract = content["data"]["customerContractDetail"]
#     assert len(customer_checkout_contract["customer"]["customerNo"]) == 7
