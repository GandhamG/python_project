import datetime

import pytest

from saleor.account.models import User
from saleor.graphql.tests.utils import (
    get_graphql_content,
    get_graphql_content_from_response,
)
from scg_checkout.models import BusinessUnit, SalesOrganization
from scgp_export.graphql.validators import validate_date
from scgp_export.models import ExportOrder
from scgp_export.tests.operations import QUERY_EXPORT_ORDERS

# def test_query_export_orders_success(
#     user1_logged,
#     customers_for_search,
#     scgp_export_pis,
#     scg_checkout_distribution_channel,
#     scg_checkout_sales_organization,
#     scg_checkout_division,
#     scg_checkout_sales_group,
#     scg_checkout_sales_office,
#     scgp_export_orders,
# ):
#     new_bu = BusinessUnit.objects.bulk_create(
#         [
#             BusinessUnit(name="KK"),
#         ]
#     )
#     new_company = SalesOrganization.objects.bulk_create(
#         [
#             SalesOrganization(name="1", code="1", business_unit=new_bu[0]),
#         ]
#     )
#     new_order_1 = ExportOrder.objects.get(id=scgp_export_orders[4].id)
#     new_order_1.sales_organization = new_company[0]
#     new_order_1.save()

#     new_order_2 = ExportOrder.objects.get(id=scgp_export_orders[5].id)
#     new_order_2.sales_organization = new_company[0]
#     new_order_2.save()

#     new_order_3 = ExportOrder.objects.get(id=scgp_export_orders[6].id)
#     new_order_3.sales_organization = new_company[0]
#     new_order_3.save()

#     variables = {
#         "sortBy": {"direction": "ASC", "field": "PI_NO"},
#         "filter": {
#             "eoNo": "2841999",
#         },
#         "first": 50,
#     }
#     response = user1_logged.post_graphql(QUERY_EXPORT_ORDERS, variables)
#     content = get_graphql_content_from_response(response)
#     total_order = ExportOrder.objects.filter(eo_no="2841999").count()
#     result = content["data"]["exportOrders"]["edges"]

#     assert result[0]["node"]["id"] == str(new_order_1.id)
#     assert result[0]["node"]["pi"]["code"] == new_order_1.pi.code
#     assert result[0]["node"]["eoNo"] == new_order_1.eo_no
#     assert result[0]["node"]["poNo"] == new_order_1.po_no

#     assert result[1]["node"]["id"] == str(new_order_2.id)
#     assert result[1]["node"]["pi"]["code"] == new_order_2.pi.code
#     assert result[1]["node"]["eoNo"] == new_order_2.eo_no
#     assert result[1]["node"]["poNo"] == new_order_2.po_no

#     assert result[2]["node"]["id"] == str(new_order_3.id)
#     assert result[2]["node"]["pi"]["code"] == new_order_3.pi.code
#     assert result[2]["node"]["eoNo"] == new_order_3.eo_no
#     assert result[2]["node"]["poNo"] == new_order_3.po_no

#     assert len(result) == total_order


def test_query_export_orders_none(
    user1_logged,
    customers_for_search,
    scgp_export_pis,
    scg_checkout_distribution_channel,
    scg_checkout_sales_organization,
    scg_checkout_division,
    scg_checkout_sales_group,
    scg_checkout_sales_office,
    scgp_export_orders,
):
    bu = BusinessUnit.objects.bulk_create(
        [
            BusinessUnit(name="KK"),
        ]
    )
    company = SalesOrganization.objects.bulk_create(
        [
            SalesOrganization(name="1", code="1", business_unit=bu[0]),
        ]
    )
    new_order = ExportOrder.objects.get(id=scgp_export_orders[5].id)
    new_order.sales_organization = company[0]
    new_order.save()

    variables = {
        "sortBy": {"direction": "DESC", "field": "PI_NO"},
        "filter": {"piNo": "pi_666", "poNo": "TL-032021", "eoNo": "2841666"},
        "first": 50,
    }
    pi_no = variables["filter"].get("piNo")
    po_no = variables["filter"].get("poNo")
    eo_no = variables["filter"].get("eoNo")
    response = user1_logged.post_graphql(QUERY_EXPORT_ORDERS, variables)
    content = get_graphql_content(response)

    order = ExportOrder.objects.filter(pi__code=pi_no, po_no=po_no, eo_no=eo_no).count()
    result = content["data"]["exportOrders"]["edges"]

    assert len(result) == order


def test_query_export_orders_must_select_create_date(
    staff_api_client,
    scgp_export_pis,
    scg_checkout_distribution_channel,
    scg_checkout_sales_organization,
    scg_checkout_division,
    scg_checkout_sales_group,
    scg_checkout_sales_office,
    scgp_export_orders,
):
    new_user = User.objects.bulk_create(
        [
            User(
                first_name="Khai",
                last_name="Dang",
                email="khai@example.com",
                is_staff=True,
                is_active=True,
            ),
        ]
    )
    new_bu = BusinessUnit.objects.bulk_create([BusinessUnit(name="KK")])
    new_company = SalesOrganization.objects.bulk_create(
        [SalesOrganization(name="1", code="1", business_unit=new_bu[0])]
    )
    new_order = ExportOrder.objects.get(id=scgp_export_orders[5].id)
    new_order.create_by = new_user[0]
    new_order.sales_organization = new_company[0]
    new_order.save()
    variables = {
        "sortBy": {"direction": "DESC", "field": "PI_NO"},
        "filter": {
            "bu": "KK",
            "status": ["DRAFT", "CONFIRMED"],
            "statusSap": ["COMPLETE", "BEING_PROCESS"],
        },
        "first": 50,
    }
    response = staff_api_client.post_graphql(QUERY_EXPORT_ORDERS, variables)
    content = get_graphql_content_from_response(response)
    result = content["errors"][0]

    assert result["message"] == "Create Date must be selected"


def test_query_export_orders_must_select_another_criteria(
    staff_api_client,
    scgp_export_pis,
    scg_checkout_distribution_channel,
    scg_checkout_sales_organization,
    scg_checkout_division,
    scg_checkout_sales_group,
    scg_checkout_sales_office,
    scgp_export_orders,
):
    new_user = User.objects.bulk_create(
        [
            User(
                first_name="Testtt",
                last_name="Test",
                email="test@example.com",
                is_staff=True,
                is_active=True,
            ),
        ]
    )
    bu = BusinessUnit.objects.bulk_create([BusinessUnit(name="TT")])
    company = SalesOrganization.objects.bulk_create(
        [SalesOrganization(name="SKT", code="1", business_unit=bu[0])]
    )
    order = ExportOrder.objects.get(id=scgp_export_orders[4].id)
    order.create_by = new_user[0]
    order.sales_organization = company[0]
    order.save()
    variables = {
        "sortBy": {"direction": "DESC", "field": "PI_NO"},
        "filter": {"createDate": {"gte": "2022-04-02", "lte": "2022-04-22"}},
        "first": 50,
    }
    response = staff_api_client.post_graphql(QUERY_EXPORT_ORDERS, variables)
    content = get_graphql_content_from_response(response)
    result = content["errors"][0]

    assert result["message"] == "Must select another criteria"


def test_validate_date_end_date_greater_than_start_date():
    start_date = datetime.datetime(2022, 8, 20)
    end_date = datetime.datetime(2022, 7, 20)
    message = "End Date must be greater than Start Date"
    with pytest.raises(Exception) as e:
        validate_date(start_date, end_date)
    assert message == str(e.value.args[0])


def test_validate_date_max_one_year():
    start_date = datetime.datetime(2022, 8, 20)
    end_date = datetime.datetime(2024, 12, 21)
    message = "Period of Start Date - End Date maximum to 1 year"
    with pytest.raises(Exception) as e:
        validate_date(start_date, end_date)
    assert message == str(e.value.args[0])


def test_validate_date_max_one_year_leap_year():
    start_date = datetime.datetime(2020, 2, 20)
    end_date = datetime.datetime(2021, 2, 22)
    message = "Period of Start Date - End Date maximum to 1 year"
    with pytest.raises(Exception) as e:
        validate_date(start_date, end_date)
    assert message == str(e.value.args[0])
