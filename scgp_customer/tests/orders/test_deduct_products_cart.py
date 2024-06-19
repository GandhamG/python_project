from scgp_customer.implementations.orders import deduct_quantity_cart_item
from scgp_customer.models import CustomerCartItem, CustomerOrderLine


def test_deduct_quantity_cart_item_success(
    customers_for_search,
    scgp_customer_carts,
    scgp_customer_cart_items,
    scgp_customer_orders,
    scgp_customer_order_lines,
):
    order_id = scgp_customer_orders[3].id
    user = customers_for_search[2]
    remain_quantity = (
        CustomerCartItem.objects.get(id=scgp_customer_cart_items[6].id).quantity
        - CustomerOrderLine.objects.get(id=scgp_customer_order_lines[3].id).quantity
    )
    deduct_quantity_cart_item(order_id, user)
    assert CustomerCartItem.objects.get(
        id=scgp_customer_cart_items[6].id
    ).quantity == float(remain_quantity)


def test_deduct_quantity_cart_item_less_than_order_line(
    scgp_customer_contract_products,
    scgp_customer_product_variants,
    customers_for_search,
    scgp_customer_carts,
    scgp_customer_cart_items,
    scgp_customer_orders,
    scgp_customer_order_lines,
):
    order_id = scgp_customer_orders[3].id
    user = customers_for_search[2]
    deduct_quantity_cart_item(order_id, user)
    assert (
        CustomerCartItem.objects.filter(id=scgp_customer_cart_items[7].id).first()
        is None
    )
    assert (
        CustomerOrderLine.objects.filter(id=scgp_customer_order_lines[4].id)
        .first()
        .cart_item_id
        is None
    )


def test_deduct_quantity_cart_item_equal_order_line(
    scgp_customer_contract_products,
    scgp_customer_product_variants,
    customers_for_search,
    scgp_customer_carts,
    scgp_customer_cart_items,
    scgp_customer_orders,
    scgp_customer_order_lines,
):
    order_id = scgp_customer_orders[3].id
    user = customers_for_search[2]
    deduct_quantity_cart_item(order_id, user)
    assert (
        CustomerCartItem.objects.filter(id=scgp_customer_cart_items[8].id).first()
        is None
    )
    assert (
        CustomerOrderLine.objects.filter(id=scgp_customer_order_lines[5].id)
        .first()
        .cart_item_id
        is None
    )
