from django.db.models import Q

from saleor.graphql.tests.utils import get_graphql_content
from scgp_export.models import ExportSoldTo
from scgp_export.tests.operations import (
    FILTER_SOLD_TO_EXPORT_ORDER,
)  # FILTER_BUSINESS_EXPORT_ORDER,; FILTER_COMPANIES_EXPORT_ORDER_BY_BUSINESS_UNIT,; FILTER_COMPANIES_EXPORT_ORDER_BY_USER_LOGIN,

# def test_filter_business_unit(staff_api_client, business_units_for_search):
#     variables = {}
#     response = staff_api_client.post_graphql(
#         FILTER_BUSINESS_EXPORT_ORDER,
#         variables,
#     )
#     content = get_graphql_content(response)
#     business_units = content["data"]["filterBusinessExportOrder"]
#     assert len(business_units) == len(business_units_for_search)


# def test_filter_company_selected_business_1(
#     staff_api_client,
#     business_units_for_search,
#     scg_export_order_sales_organization_by_business_unit,
# ):
#     variables = {"first": 30, "filter": {"search": "pp"}}
#     response = staff_api_client.post_graphql(
#         FILTER_COMPANIES_EXPORT_ORDER_BY_BUSINESS_UNIT,
#         variables,
#     )
#     content = get_graphql_content(response)
#     companies = content["data"]["filterCompaniesExportOrderByBusinessUnit"]["edges"]
#     assert len(companies) == 2


# def test_filter_company_selected_business_2(
#     staff_api_client,
#     business_units_for_search,
#     scg_export_order_sales_organization_by_business_unit,
# ):
#     variables = {"first": 30, "filter": {"search": "p"}}
#     response = staff_api_client.post_graphql(
#         FILTER_COMPANIES_EXPORT_ORDER_BY_BUSINESS_UNIT,
#         variables,
#     )
#     content = get_graphql_content(response)
#     companies = content["data"]["filterCompaniesExportOrderByBusinessUnit"]["edges"]
#     assert len(companies) == 4


# def test_filter_company_not_selected_business(
#     staff_api_client,
#     business_units_for_search,
#     scg_export_order_sales_organization_by_business_unit,
# ):
#     variables = {}
#     response = staff_api_client.post_graphql(
#         FILTER_COMPANIES_EXPORT_ORDER_BY_USER_LOGIN,
#         variables,
#     )
#     content = get_graphql_content(response)
#     assert len(content["data"]["filterCompaniesExportOrderByUserLogin"]) == 6


# def test_filter_export_sold_to_by_code_1(api_client, scgp_export_sold_tos):
#     search = ""
#     variables = {"filter": {"search": search}, "first": 30}

#     response = api_client.post_graphql(FILTER_SOLD_TO_EXPORT_ORDER, variables)
#     content = get_graphql_content(response)
#     export_sold_tos = content["data"]["filterSoldToExportOrder"]

#     expect_sold_tos = list(
#         ExportSoldTo.objects.filter(
#             Q(name__icontains=search) | Q(code__icontains=search)
#         )
#     )
#     assert len(export_sold_tos["edges"]) == len(expect_sold_tos)
#     assert export_sold_tos["edges"][0]["node"]["name"] == expect_sold_tos[0].name


# def test_filter_export_sold_to_by_code_2(api_client, scgp_export_sold_tos):
#     search = "1"
#     variables = {"filter": {"search": search}, "first": 30}

#     response = api_client.post_graphql(FILTER_SOLD_TO_EXPORT_ORDER, variables)
#     content = get_graphql_content(response)
#     export_sold_tos = content["data"]["filterSoldToExportOrder"]

#     expect_sold_tos = list(
#         ExportSoldTo.objects.filter(
#             Q(name__icontains=search) | Q(code__icontains=search)
#         )
#     )
#     assert len(export_sold_tos["edges"]) == len(expect_sold_tos)
#     assert export_sold_tos["edges"][0]["node"]["name"] == expect_sold_tos[0].name


def test_filter_export_sold_to_by_code_fail(api_client, scgp_export_sold_tos):
    search = "hello"
    variables = {"filter": {"search": search}, "first": 30}
    response = api_client.post_graphql(FILTER_SOLD_TO_EXPORT_ORDER, variables)
    content = get_graphql_content(response)
    export_sold_tos = content["data"]["filterSoldToExportOrder"]

    expect_sold_tos = list(
        ExportSoldTo.objects.filter(
            Q(name__icontains=search) | Q(code__icontains=search)
        )
    )
    assert len(export_sold_tos["edges"]) == len(expect_sold_tos)


# def test_filter_export_sold_to_by_name_1(api_client, scgp_export_sold_tos):
#     name_search = ""
#     variables = {"first": 10, "filter": {"search": scgp_export_sold_tos[0].name[:5]}}
#     response = api_client.post_graphql(FILTER_SOLD_TO_EXPORT_ORDER, variables)
#     content = get_graphql_content(response)
#     export_sold_tos = content["data"]["filterSoldToExportOrder"]
#     print(export_sold_tos)

#     expect_sold_tos = list(
#         ExportSoldTo.objects.filter(
#             Q(name__icontains=name_search) | Q(code__icontains=name_search)
#         )
#     )
#     assert len(export_sold_tos["edges"]) == len(expect_sold_tos)
#     assert export_sold_tos["edges"][0]["node"]["name"] == expect_sold_tos[0].name


# def test_filter_export_sold_to_by_name_2(api_client, scgp_export_sold_tos):
#     name_search = scgp_export_sold_tos[0].name[:5]
#     variables = {"first": 10, "filter": {"search": scgp_export_sold_tos[0].name[:5]}}
#     response = api_client.post_graphql(FILTER_SOLD_TO_EXPORT_ORDER, variables)
#     content = get_graphql_content(response)
#     export_sold_tos = content["data"]["filterSoldToExportOrder"]
#     print(export_sold_tos)

#     expect_sold_tos = list(
#         ExportSoldTo.objects.filter(
#             Q(name__icontains=name_search) | Q(code__icontains=name_search)
#         )
#     )
#     assert len(export_sold_tos["edges"]) == len(expect_sold_tos)
#     assert export_sold_tos["edges"][0]["node"]["name"] == expect_sold_tos[0].name


def test_filter_export_sold_to_by_name_fail(api_client, scgp_export_sold_tos):
    name_search = "My name is Hello"
    variables = {"first": 10, "filter": {"search": name_search}}
    response = api_client.post_graphql(FILTER_SOLD_TO_EXPORT_ORDER, variables)
    content = get_graphql_content(response)
    export_sold_tos = content["data"]["filterSoldToExportOrder"]

    expect_sold_tos = list(
        ExportSoldTo.objects.filter(
            Q(name__icontains=name_search) | Q(code__icontains=name_search)
        )
    )
    assert len(export_sold_tos["edges"]) == len(expect_sold_tos)
