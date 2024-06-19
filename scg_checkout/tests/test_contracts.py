# from saleor.graphql.tests.utils import get_graphql_content
# from scg_checkout.tests.operations import CONTRACTS_QUERY


# def test_contracts_query(
#     staff_api_client,
#     contracts_for_search,
#     companies_for_search,
#     customers_for_search,
#     contract_products_for_search,
# ):
#     variables = {
#         "customerId": customers_for_search[0].id,
#         "first": 10,
#         "contractIds": [contract.pk for contract in contracts_for_search],
#         "filter": {
#             "companyIds": [company.pk for company in companies_for_search],
#         },
#         "productSort": {"direction": "ASC", "field": "REMAIN"},
#     }

#     response = staff_api_client.post_graphql(
#         CONTRACTS_QUERY,
#         variables,
#     )

#     content = get_graphql_content(response)
#     contracts = content["data"]["contracts"]["edges"]

#     assert len(contracts) == 3
#     assert contracts[0]["node"]["id"] == str(contracts_for_search[0].id)
#     assert contracts[1]["node"]["customer"]["id"] == str(customers_for_search[0].id)
#     assert contracts[0]["node"]["company"]["id"] == str(companies_for_search[0].id)
#     assert len(contracts[0]["node"]["products"]) == 5
#     assert (
#         contracts[0]["node"]["products"][0]["remain"]
#         <= contracts[0]["node"]["products"][1]["remain"]
#     )
#     assert (
#         contracts[0]["node"]["products"][2]["remain"]
#         <= contracts[0]["node"]["products"][3]["remain"]
#     )
