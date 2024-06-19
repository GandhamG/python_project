# from saleor.graphql.tests.utils import get_graphql_content
# from scg_checkout.tests.operations import BUSINESS_UNITS_QUERY


# def test_business_units_query(
#     staff_api_client,
#     business_units_for_search,
#     companies_for_search,
# ):
#     variables = {"first": 10}
#     response = staff_api_client.post_graphql(
#         BUSINESS_UNITS_QUERY,
#         variables,
#     )

#     content = get_graphql_content(response)
#     business_units = content["data"]["businessUnits"]["edges"]

#     assert len(business_units) == len(business_units_for_search)
#     assert business_units[0]["node"]["id"] == str(business_units_for_search[0].id)
#     assert len(business_units[0]["node"]["companies"]) == 2
#     assert business_units[0]["node"]["companies"][0]["id"] == str(
#         companies_for_search[0].id
#     )
