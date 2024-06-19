from saleor.graphql.tests.utils import (
    get_graphql_content_from_response,
)  # get_graphql_content,
from scgp_export.models import ExportCart, ExportCartItem
from scgp_export.tests.operations import (  # EXPORT_CARTS_QUERY,
    DELETE_EXPORT_CART_ITEMS,
    EXPORT_CART_ITEMS_QUERY,
)

# def test_export_carts(
#     customers_for_search,
#     user1_logged,
#     scgp_export_sold_tos,
#     scgp_export_pi_products,
#     scgp_export_carts,
#     scgp_export_cart_items,
# ):
#     variables = {"first": 5}
#     response = user1_logged.post_graphql(
#         EXPORT_CARTS_QUERY,
#         variables,
#     )
#     content = get_graphql_content(response)
#     customer = customers_for_search[0]
#     exports_carts = content["data"]["exportCarts"]
#     assert (
#         exports_carts["totalPi"]
#         == ExportCart.objects.filter(created_by=customer).count()
#     )
#     assert (
#         exports_carts["totalSoldTo"]
#         == ExportCart.objects.filter(created_by=customer)
#         .distinct("sold_to__id")
#         .count()
#     )
#     assert (
#         exports_carts["totalCartItem"]
#         == ExportCartItem.objects.filter(cart__created_by=customer).count()
#     )

#     assert exports_carts["totalCartItem"] == sum(
#         [edge["node"]["totalItems"] for edge in exports_carts["carts"]["edges"]]
#     )


# def test_export_carts_not_logged(
#     customers_for_search,
#     api_client,
#     scgp_export_sold_tos,
#     scgp_export_pi_products,
#     scgp_export_carts,
#     scgp_export_cart_items,
# ):
#     variables = {"first": 5}
#     response = api_client.post_graphql(
#         EXPORT_CARTS_QUERY,
#         variables,
#     )

#     content = get_graphql_content_from_response(response)
#     message = "You need to log in"
#     assert content["errors"][0]["message"] == message


# def test_export_cart_items(
#     customers_for_search,
#     user1_logged,
#     scgp_export_sold_tos,
#     scgp_export_pi_products,
#     scgp_export_carts,
#     scgp_export_cart_items,
# ):
#     variables = {"id": scgp_export_carts[0].id, "first": 5}
#     response = user1_logged.post_graphql(
#         EXPORT_CART_ITEMS_QUERY,
#         variables,
#     )
#     content = get_graphql_content(response)
#     export_cart = content["data"]["exportCart"]
#     edges = export_cart["items"]["edges"]
#     assert ExportCartItem.objects.filter(
#         cart__id=scgp_export_carts[0].id
#     ).count() == len(edges)


def test_export_cart_item_not_login(
    customers_for_search,
    api_client,
    scgp_export_sold_tos,
    scgp_export_pi_products,
    scgp_export_carts,
    scgp_export_cart_items,
):
    variables = {"id": scgp_export_carts[0].id, "first": 5}
    response = api_client.post_graphql(
        EXPORT_CART_ITEMS_QUERY,
        variables,
    )
    content = get_graphql_content_from_response(response)
    message = "You need to log in"
    assert content["errors"][0]["message"] == message


# def test_delete_cart_items(
#     customers_for_search,
#     user1_logged,
#     scgp_export_sold_tos,
#     scgp_export_pi_products,
#     scgp_export_carts,
#     scgp_export_cart_items,
# ):
#     export_cart_item_before_delete = ExportCartItem.objects.filter(
#         cart__created_by=customers_for_search[0]
#     ).count()
#     export_cart_before_delete = ExportCart.objects.filter(
#         created_by=customers_for_search[0]
#     ).count()
#     variables = {
#         "cartItemIds": [scgp_export_cart_items[1].id, scgp_export_cart_items[0].id]
#     }
#     response = user1_logged.post_graphql(
#         DELETE_EXPORT_CART_ITEMS,
#         variables,
#     )
#     content = get_graphql_content(response)
#     export_cart_item_after_delete = ExportCartItem.objects.filter(
#         cart__created_by=customers_for_search[0]
#     ).count()
#     export_cart_after_delete = ExportCart.objects.filter(
#         created_by=customers_for_search[0]
#     ).count()
#     assert content["data"]["deleteExportCartItems"]["status"] == "true"
#     assert export_cart_item_after_delete == export_cart_item_before_delete - 2
#     assert export_cart_after_delete == export_cart_before_delete


# def test_delete_cart_item(
#     customers_for_search,
#     user1_logged,
#     scgp_export_sold_tos,
#     scgp_export_pi_products,
#     scgp_export_carts,
#     scgp_export_cart_items,
# ):
#     export_cart_item_before_delete = ExportCartItem.objects.filter(
#         cart__created_by=customers_for_search[0]
#     ).count()
#     export_cart_before_delete = ExportCart.objects.filter(
#         created_by=customers_for_search[0]
#     ).count()
#     variables = {"cartItemIds": [scgp_export_cart_items[1].id]}
#     response = user1_logged.post_graphql(
#         DELETE_EXPORT_CART_ITEMS,
#         variables,
#     )
#     content = get_graphql_content(response)
#     export_cart_item_after_delete = ExportCartItem.objects.filter(
#         cart__created_by=customers_for_search[0]
#     ).count()
#     export_cart_after_delete = ExportCart.objects.filter(
#         created_by=customers_for_search[0]
#     ).count()
#     assert content["data"]["deleteExportCartItems"]["status"] == "true"
#     assert export_cart_item_after_delete == export_cart_item_before_delete - 1
#     assert export_cart_after_delete == export_cart_before_delete


def test_delete_cart_items_not_log_in(
    customers_for_search,
    api_client,
    scgp_export_sold_tos,
    scgp_export_pi_products,
    scgp_export_carts,
    scgp_export_cart_items,
):
    variables = {
        "cartItemIds": [scgp_export_cart_items[1].id, scgp_export_cart_items[6].id]
    }
    response = api_client.post_graphql(
        DELETE_EXPORT_CART_ITEMS,
        variables,
    )
    get_graphql_content_from_response(response)
    assert ExportCartItem.objects.count() == len(scgp_export_cart_items)


def test_delete_cart_items_not_belong_to_user(
    customers_for_search,
    user1_logged,
    scgp_export_sold_tos,
    scgp_export_pi_products,
    scgp_export_carts,
    scgp_export_cart_items,
):
    export_cart_item_before_delete = ExportCartItem.objects.filter(
        cart__created_by=customers_for_search[0]
    ).count()
    export_cart_before_delete = ExportCart.objects.filter(
        created_by=customers_for_search[0]
    ).count()
    variables = {
        "cartItemIds": [scgp_export_cart_items[0].id, scgp_export_cart_items[6].id]
    }
    response = user1_logged.post_graphql(
        DELETE_EXPORT_CART_ITEMS,
        variables,
    )
    get_graphql_content_from_response(response)
    export_cart_item_after_delete = ExportCartItem.objects.filter(
        cart__created_by=customers_for_search[0]
    ).count()
    export_cart_after_delete = ExportCart.objects.filter(
        created_by=customers_for_search[0]
    ).count()
    assert export_cart_item_before_delete == export_cart_item_after_delete
    assert export_cart_before_delete == export_cart_after_delete


def test_delete_cart_items_wrong_range_id(
    customers_for_search,
    user1_logged,
    scgp_export_sold_tos,
    scgp_export_pi_products,
    scgp_export_carts,
    scgp_export_cart_items,
):
    export_cart_item_before_delete = ExportCartItem.objects.filter(
        cart__created_by=customers_for_search[0]
    ).count()
    export_cart_before_delete = ExportCart.objects.filter(
        created_by=customers_for_search[0]
    ).count()
    variables = {"cartItemIds": [scgp_export_cart_items[0].id, 9]}
    response = user1_logged.post_graphql(
        DELETE_EXPORT_CART_ITEMS,
        variables,
    )
    get_graphql_content_from_response(response)
    export_cart_item_after_delete = ExportCartItem.objects.filter(
        cart__created_by=customers_for_search[0]
    ).count()
    export_cart_after_delete = ExportCart.objects.filter(
        created_by=customers_for_search[0]
    ).count()
    assert export_cart_item_before_delete == export_cart_item_after_delete
    assert export_cart_before_delete == export_cart_after_delete


def test_delete_cart_items_wrong_range(
    customers_for_search,
    user1_logged,
    scgp_export_sold_tos,
    scgp_export_pi_products,
    scgp_export_carts,
    scgp_export_cart_items,
):
    export_cart_item_before_delete = ExportCartItem.objects.filter(
        cart__created_by=customers_for_search[0]
    ).count()
    export_cart_before_delete = ExportCart.objects.filter(
        created_by=customers_for_search[0]
    ).count()
    variables = {"cartItemIds": [99]}
    response = user1_logged.post_graphql(
        DELETE_EXPORT_CART_ITEMS,
        variables,
    )
    get_graphql_content_from_response(response)
    export_cart_item_after_delete = ExportCartItem.objects.filter(
        cart__created_by=customers_for_search[0]
    ).count()
    export_cart_after_delete = ExportCart.objects.filter(
        created_by=customers_for_search[0]
    ).count()
    assert export_cart_item_before_delete == export_cart_item_after_delete
    assert export_cart_before_delete == export_cart_after_delete
