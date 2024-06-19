# from saleor.graphql.tests.utils import (
#     assert_graphql_error_with_message,
#     get_graphql_content,
# )
# from scgp_export.graphql.enums import ScgpExportOrderStatus
# from scgp_export.models import ExportOrderLine, ExportPIProduct
# from scgp_export.tests.operations import DELETE_EXPORT_ORDER_LINES_MUTATION


# def test_delete_export_order_lines_success(
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
#     variables = {
#         "ids": [scgp_export_order_lines[0].id, scgp_export_order_lines[1].id],
#         "deleteAll": False,
#         "orderId": scgp_export_orders[0].id,
#     }
#     response = user1_logged.post_graphql(DELETE_EXPORT_ORDER_LINES_MUTATION, variables)
#     content = get_graphql_content(response)
#     errors = content["data"]["deleteExportOrderLines"]["errors"]
#     assert len(errors) == 0
#     assert (
#         ExportOrderLine.objects.filter(
#             id__in=[scgp_export_order_lines[0].id, scgp_export_order_lines[1].id]
#         ).count()
#         == 0
#     )


# def test_delete_export_order_lines_success_for_confirmed_order(
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
#     old_order_line_qty = scgp_export_order_lines[6].quantity
#     old_remaining_qty = scgp_export_order_lines[6].pi_product.remaining_quantity
#     pi_product_id = scgp_export_order_lines[6].pi_product.id
#     variables = {
#         "ids": [scgp_export_order_lines[6].id],
#         "deleteAll": False,
#         "orderId": scgp_export_orders[2].id,
#     }
#     response = user1_logged.post_graphql(DELETE_EXPORT_ORDER_LINES_MUTATION, variables)
#     content = get_graphql_content(response)
#     errors = content["data"]["deleteExportOrderLines"]["errors"]
#     assert len(errors) == 0
#     assert (
#         ExportOrderLine.objects.filter(id__in=[scgp_export_order_lines[6].id]).count()
#         == 0
#     )
#     assert scgp_export_orders[2].status == ScgpExportOrderStatus.CONFIRMED.value
#     pi_product = ExportPIProduct.objects.get(id=pi_product_id)
#     assert pi_product.remaining_quantity == float(old_remaining_qty) + float(
#         old_order_line_qty
#     )


# def test_delete_all_export_order_lines_success_for_confirmed_order(
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
#     old_order_line_qty = scgp_export_order_lines[6].quantity
#     old_remaining_qty = scgp_export_order_lines[6].pi_product.remaining_quantity
#     pi_product_id = scgp_export_order_lines[6].pi_product.id
#     variables = {
#         "ids": [],
#         "deleteAll": True,
#         "orderId": scgp_export_orders[2].id,
#     }
#     response = user1_logged.post_graphql(DELETE_EXPORT_ORDER_LINES_MUTATION, variables)
#     content = get_graphql_content(response)
#     errors = content["data"]["deleteExportOrderLines"]["errors"]
#     assert len(errors) == 0
#     assert (
#         ExportOrderLine.objects.filter(order_id=scgp_export_orders[2].id).count() == 0
#     )
#     assert scgp_export_orders[2].status == ScgpExportOrderStatus.CONFIRMED.value
#     pi_product = ExportPIProduct.objects.get(id=pi_product_id)
#     assert pi_product.remaining_quantity == float(old_remaining_qty) + float(
#         old_order_line_qty
#     )


# def test_export_order_line_not_exist(
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
# ):
#     variables = {
#         "ids": [1000],
#         "deleteAll": False,
#         "orderId": scgp_export_orders[0].id,
#     }
#     response = user1_logged.post_graphql(DELETE_EXPORT_ORDER_LINES_MUTATION, variables)
#     message = "you dont have permission to delete other's order line"
#     assert_graphql_error_with_message(response, message)


# def test_delete_export_order_lines_all_lines_success(
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
# ):
#     variables = {"ids": [], "deleteAll": True, "orderId": scgp_export_orders[0].id}
#     response = user1_logged.post_graphql(DELETE_EXPORT_ORDER_LINES_MUTATION, variables)
#     content = get_graphql_content(response)
#     errors = content["data"]["deleteExportOrderLines"]["errors"]
#     assert len(errors) == 0
#     assert (
#         ExportOrderLine.objects.filter(order_id=scgp_export_orders[0].id).count() == 0
#     )


# def test_delete_export_order_lines_all_lines_not_exist(
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
# ):
#     variables = {"ids": [], "deleteAll": True, "orderId": 100}
#     response = user1_logged.post_graphql(DELETE_EXPORT_ORDER_LINES_MUTATION, variables)
#     message = "ExportOrder matching query does not exist."
#     assert_graphql_error_with_message(response, message)
