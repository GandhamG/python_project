# from saleor.graphql.tests.utils import get_graphql_content
# from scg_checkout.tests.operations import CONTRACT_QUERY


# def test_contract_query(
#     staff_api_client,
#     contracts_for_search,
#     contract_products_for_search,
# ):
#     variables = {
#         "contractId": contracts_for_search[0].id,
#         "productSort": {"direction": "DESC", "field": "REMAIN"},
#     }
#     response = staff_api_client.post_graphql(
#         CONTRACT_QUERY,
#         variables,
#     )

#     content = get_graphql_content(response)
#     contract = content["data"]["contract"]

#     assert contracts_for_search[0].project_name == contract["projectName"]
#     assert len(contract["products"]) == 5
#     assert contract["products"][0]["remain"] >= contract["products"][1]["remain"]
#     assert contract["products"][2]["remain"] >= contract["products"][3]["remain"]
