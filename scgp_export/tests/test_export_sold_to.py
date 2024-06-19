from django.db.models import Q

from saleor.graphql.tests.utils import get_graphql_content
from scgp_export.models import ExportSoldTo
from scgp_export.tests.operations import EXPORT_SOLD_TOS_QUERY

# def test_filter_export_sold_to_by_code(
#     api_client, scgp_export_sold_tos, scgp_export_pis
# ):
#     code_search = scgp_export_sold_tos[0].code[:5]
#     variables = {
#         "first": 2,
#         "search": code_search,
#     }
#     response = api_client.post_graphql(EXPORT_SOLD_TOS_QUERY, variables)
#     content = get_graphql_content(response)
#     export_sold_tos = content["data"]["exportSoldTos"]

#     expect_sold_tos = list(
#         ExportSoldTo.objects.filter(
#             Q(name__icontains=code_search) | Q(code__icontains=code_search)
#         )
#     )

#     assert export_sold_tos["totalCount"] == len(expect_sold_tos)
#     assert len(export_sold_tos["edges"]) == len(expect_sold_tos[:2])
#     assert export_sold_tos["edges"][0]["node"]["name"] == expect_sold_tos[0].name


def test_filter_export_sold_to_by_code_fail(
    api_client, scgp_export_sold_tos, scgp_export_pis
):
    code_search = "Sold to code not in db"
    variables = {
        "first": 2,
        "search": code_search,
    }
    response = api_client.post_graphql(EXPORT_SOLD_TOS_QUERY, variables)
    content = get_graphql_content(response)
    export_sold_tos = content["data"]["exportSoldTos"]

    expect_sold_tos = list(
        ExportSoldTo.objects.filter(
            Q(name__icontains=code_search) | Q(code__icontains=code_search)
        )
    )

    assert len(export_sold_tos["edges"]) == len(expect_sold_tos)


# def test_filter_export_sold_to_by_name(
#     api_client, scgp_export_sold_tos, scgp_export_pis
# ):
#     name_search = scgp_export_sold_tos[0].name[:5]
#     variables = {
#         "first": 2,
#         "search": scgp_export_sold_tos[0].name[:5],
#     }
#     response = api_client.post_graphql(EXPORT_SOLD_TOS_QUERY, variables)
#     content = get_graphql_content(response)
#     export_sold_tos = content["data"]["exportSoldTos"]

#     expect_sold_tos = list(
#         ExportSoldTo.objects.filter(
#             Q(name__icontains=name_search) | Q(code__icontains=name_search)
#         )
#     )

#     assert export_sold_tos["totalCount"] == len(expect_sold_tos)
#     assert export_sold_tos["edges"][0]["node"]["name"] == expect_sold_tos[0].name


def test_filter_export_sold_to_by_name_fail(
    api_client, scgp_export_sold_tos, scgp_export_pis
):
    name_search = "Sold to name not in db"
    variables = {
        "first": 2,
        "search": "Sold to name not in db",
    }
    response = api_client.post_graphql(EXPORT_SOLD_TOS_QUERY, variables)
    content = get_graphql_content(response)
    export_sold_tos = content["data"]["exportSoldTos"]

    expect_sold_tos = list(
        ExportSoldTo.objects.filter(
            Q(name__icontains=name_search) | Q(code__icontains=name_search)
        )
    )

    assert len(export_sold_tos["edges"]) == len(expect_sold_tos)
