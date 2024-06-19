# from saleor.graphql.tests.utils import get_graphql_content
# from scgp_export.graphql.enums import ScgpExportOrderStatus
# from scgp_export.models import ExportOrderLine, ExportPIProduct
# from scgp_export.tests.operations import ADD_PRODUCT_TO_EXPORT_ORDER_MUTATION


# def test_add_product_to_order_success_with_new_product(
#     user1_logged,
#     customers_for_search,
#     scg_checkout_distribution_channel,
#     scg_checkout_sales_organization,
#     scg_checkout_division,
#     scg_checkout_sales_office,
#     scg_checkout_sales_group,
#     scgp_export_pis,
#     scgp_export_orders,
#     scgp_export_order_lines,
#     scgp_export_pi_products,
# ):
#     current_total_lines = ExportOrderLine.objects.filter(
#         order_id=scgp_export_orders[1].id
#     ).count()
#     variable = {
#         "id": scgp_export_orders[1].id,
#         "input": [
#             {
#                 "piProduct": scgp_export_pi_products[3].id,
#                 "quantity": 12,
#             },
#             {
#                 "piProduct": scgp_export_pi_products[4].id,
#                 "quantity": 10,
#             },
#         ],
#     }

#     response = user1_logged.post_graphql(ADD_PRODUCT_TO_EXPORT_ORDER_MUTATION, variable)
#     content = get_graphql_content(response)
#     errors = content["data"]["addProductsToExportOrder"]["errors"]
#     assert len(errors) == 0
#     assert (
#         ExportOrderLine.objects.filter(order_id=scgp_export_orders[1].id).count()
#         == current_total_lines + 2
#     )


# def test_add_product_to_order_success_with_old_product(
#     user1_logged,
#     customers_for_search,
#     scg_checkout_distribution_channel,
#     scg_checkout_sales_organization,
#     scg_checkout_division,
#     scg_checkout_sales_office,
#     scg_checkout_sales_group,
#     scgp_export_pis,
#     scgp_export_orders,
#     scgp_export_order_lines,
#     scgp_export_pi_products,
# ):
#     current_total_lines = ExportOrderLine.objects.filter(
#         order_id=scgp_export_orders[1].id
#     ).count()

#     current_quantity = (
#         ExportOrderLine.objects.filter(
#             order_id=scgp_export_orders[1].id, pi_product_id=scgp_export_orders[0].id
#         )
#         .first()
#         .quantity
#     )
#     variable = {
#         "id": scgp_export_orders[1].id,
#         "input": [
#             {
#                 "piProduct": scgp_export_pi_products[0].id,
#                 "quantity": 12,
#             },
#         ],
#     }

#     response = user1_logged.post_graphql(ADD_PRODUCT_TO_EXPORT_ORDER_MUTATION, variable)
#     content = get_graphql_content(response)
#     errors = content["data"]["addProductsToExportOrder"]["errors"]
#     assert len(errors) == 0
#     assert (
#         ExportOrderLine.objects.filter(order_id=scgp_export_orders[1].id).count()
#         == current_total_lines
#     )
#     assert ExportOrderLine.objects.filter(
#         order_id=scgp_export_orders[1].id, pi_product_id=scgp_export_orders[0].id
#     ).first().quantity == current_quantity + variable["input"][0].get("quantity")


# def test_add_product_to_order_with_confirmed_status(
#     user1_logged,
#     customers_for_search,
#     scg_checkout_distribution_channel,
#     scg_checkout_sales_organization,
#     scg_checkout_division,
#     scg_checkout_sales_office,
#     scg_checkout_sales_group,
#     scgp_export_pis,
#     scgp_export_orders,
#     scgp_export_order_lines,
#     scgp_export_pi_products,
# ):
#     old_remaining_qty = scgp_export_pi_products[0].remaining_quantity
#     variable = {
#         "id": scgp_export_orders[2].id,
#         "input": [
#             {
#                 "piProduct": scgp_export_pi_products[0].id,
#                 "quantity": 12,
#             },
#             {
#                 "piProduct": scgp_export_pi_products[3].id,
#                 "quantity": 12,
#             },
#         ],
#     }

#     response = user1_logged.post_graphql(ADD_PRODUCT_TO_EXPORT_ORDER_MUTATION, variable)
#     content = get_graphql_content(response)
#     errors = content["data"]["addProductsToExportOrder"]["errors"]
#     assert len(errors) == 0
#     assert scgp_export_orders[2].status == ScgpExportOrderStatus.CONFIRMED.value
#     pi_product = ExportPIProduct.objects.get(id=scgp_export_pi_products[0].id)
#     assert pi_product.remaining_quantity == float(old_remaining_qty) - float(
#         variable["input"][0]["quantity"]
#     )
