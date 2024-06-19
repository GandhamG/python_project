# from saleor.graphql.tests.utils import get_graphql_content
# from scgp_export.models import ExportPI
# from scgp_export.tests.operations import EXPORT_PIS_QUERY


# def test_filter_export_pi_by_code(api_client, scgp_export_sold_tos, scgp_export_pis):
#     code_search = scgp_export_pis[0].code
#     variables = {
#         "first": 2,
#         "searchCode": scgp_export_pis[0].code,
#     }
#     response = api_client.post_graphql(EXPORT_PIS_QUERY, variables)
#     content = get_graphql_content(response)
#     export_pis = content["data"]["exportPis"]["edges"]

#     expect_export_pis = list(ExportPI.objects.filter(code__icontains=code_search))

#     assert len(export_pis) == len(expect_export_pis)
#     assert export_pis[0]["node"]["code"] == expect_export_pis[0].code


# def test_filter_export_pi_by_code_fail(
#     api_client, scgp_export_sold_tos, scgp_export_pis
# ):
#     code_search = "code not in db"
#     variables = {
#         "first": 2,
#         "searchCode": code_search,
#     }
#     response = api_client.post_graphql(EXPORT_PIS_QUERY, variables)
#     content = get_graphql_content(response)
#     export_pis = content["data"]["exportPis"]["edges"]

#     expect_export_pis = list(ExportPI.objects.filter(code__icontains=code_search))

#     assert len(export_pis) == len(expect_export_pis)


# def test_filter_export_pi_by_display_text(
#     api_client, scgp_export_sold_tos, scgp_export_pis
# ):
#     sold_to_search = scgp_export_sold_tos[0].id
#     variables = {
#         "first": 2,
#         "searchSoldTo": f"{scgp_export_sold_tos[0].code} - {scgp_export_sold_tos[0].name}",
#     }
#     response = api_client.post_graphql(EXPORT_PIS_QUERY, variables)
#     content = get_graphql_content(response)
#     export_pis = content["data"]["exportPis"]["edges"]

#     expect_export_pis = list(ExportPI.objects.filter(sold_to_id=sold_to_search))

#     assert len(export_pis) == len(expect_export_pis)
#     assert export_pis[0]["node"]["soldTo"]["id"] == str(expect_export_pis[0].id)


# def test_filter_export_pi_by_sold_to_code(
#     api_client, scgp_export_sold_tos, scgp_export_pis
# ):
#     sold_to_search = scgp_export_sold_tos[0].id
#     variables = {
#         "first": 2,
#         "searchSoldTo": f"{scgp_export_sold_tos[0].code}",
#     }
#     response = api_client.post_graphql(EXPORT_PIS_QUERY, variables)
#     content = get_graphql_content(response)
#     export_pis = content["data"]["exportPis"]["edges"]

#     expect_export_pis = list(ExportPI.objects.filter(sold_to_id=sold_to_search))

#     assert len(export_pis) == len(expect_export_pis)
#     assert export_pis[0]["node"]["soldTo"]["id"] == str(expect_export_pis[0].id)


# def test_filter_export_pi_by_sold_to_fail(
#     api_client, scgp_export_sold_tos, scgp_export_pis
# ):
#     sold_to_search = 9669
#     variables = {
#         "first": 2,
#         "searchSoldTo": "huhu hihi",
#     }
#     response = api_client.post_graphql(EXPORT_PIS_QUERY, variables)
#     content = get_graphql_content(response)
#     export_pis = content["data"]["exportPis"]["edges"]

#     expect_export_pis = list(ExportPI.objects.filter(sold_to_id=sold_to_search))

#     assert len(export_pis) == len(expect_export_pis)
