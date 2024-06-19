from datetime import datetime, timedelta

import pytest

from saleor.account.models import User
from saleor.graphql.tests.fixtures import ApiClient
from scg_checkout.models import Company
from scgp_customer.graphql.enums import ScgpCustomerOrderStatus
from scgp_customer.models import (
    CustomerCart,
    CustomerCartItem,
    CustomerContract,
    CustomerContractProduct,
    CustomerOrder,
    CustomerOrderLine,
    CustomerProduct,
    CustomerProductVariant,
    SoldTo,
)


def create_date_for_test(date_number: int):
    datetime_now = datetime.utcnow().date()
    date_time_format = "%Y-%m-%d"
    return (datetime_now - timedelta(days=date_number)).strftime(date_time_format)


@pytest.fixture
def customers_for_search(db):
    return User.objects.bulk_create(
        [
            User(
                first_name="John",
                last_name="Allen",
                email="allen@example.com",
                is_staff=False,
                is_active=True,
            ),
            User(
                first_name="Joe",
                last_name="Doe",
                email="zordon01@example.com",
                is_staff=False,
                is_active=True,
            ),
            User(
                first_name="Leslie",
                last_name="Wade",
                email="leslie@example.com",
                is_staff=False,
                is_active=True,
            ),
        ]
    )


@pytest.fixture
def scgp_customer_products_for_search(db):
    return CustomerProduct.objects.bulk_create(
        [
            CustomerProduct(
                name="CA-090D",
                slug="Slug1",
            ),
            CustomerProduct(
                name="KA-ConfiDenz230D",
                slug="Slug2",
            ),
            CustomerProduct(
                name="CS - SuperFlute125D",
                slug="Slug3",
            ),
            CustomerProduct(
                name="CA - 105D",
                slug="Slug4",
            ),
            CustomerProduct(
                name="CA - 187D",
                slug="Slug5",
            ),
        ]
    )


@pytest.fixture
def scgp_sold_to_for_search(db, customers_for_search):
    user1 = User.objects.get(email="allen@example.com")
    user2 = User.objects.get(email="zordon01@example.com")
    user3 = User.objects.get(email="leslie@example.com")

    sold_to_1 = SoldTo.objects.create(
        code="1",
        name="SoldTo1",
    )
    sold_to_1.representatives.add(user1, user2)

    sold_to_2 = SoldTo.objects.create(
        code="2",
        name="SoldTo2",
    )
    sold_to_2.representatives.add(user2, user3)

    sold_to_3 = SoldTo.objects.create(
        code="3",
        name="SoldTo3",
    )
    sold_to_3.representatives.add(user3, user1)

    return [sold_to_1, sold_to_2, sold_to_3]


@pytest.fixture
def scgp_customer_contracts(db, scgp_sold_to_for_search, companies_for_search):
    return CustomerContract.objects.bulk_create(
        [
            CustomerContract(
                sold_to=SoldTo.objects.filter(code="1").first(),
                company=Company.objects.filter(name="Siam Kraft").first(),
                code="1",
                project_name="P0",
                start_date=create_date_for_test(-10),
                end_date=create_date_for_test(10),
                payment_term="card",
            ),
            CustomerContract(
                sold_to=SoldTo.objects.filter(code="2").first(),
                company=Company.objects.filter(name="Thai Cane").first(),
                code="2",
                project_name="P1",
                start_date=create_date_for_test(-9),
                end_date=create_date_for_test(9),
                payment_term="card",
            ),
            CustomerContract(
                sold_to=SoldTo.objects.filter(code="3").first(),
                company=Company.objects.filter(name="Thai Cane").first(),
                code="3",
                project_name="P2",
                start_date=create_date_for_test(-8),
                end_date=create_date_for_test(8),
                payment_term="card",
            ),
        ]
    )


@pytest.fixture
def scgp_customer_contract_product(
    db, scgp_customer_contracts, scgp_customer_products_for_search
):
    return CustomerContractProduct.objects.bulk_create(
        [
            CustomerContractProduct(
                contract=CustomerContract.objects.filter(code="1").first(),
                product=CustomerProduct.objects.filter(slug="Slug1").first(),
                total_quantity=10.1,
                remaining_quantity=10.2,
                price_per_unit=10,
                quantity_unit="TON",
                currency="USD",
                weight=9.2,
                weight_unit="Kg",
            ),
            CustomerContractProduct(
                contract=CustomerContract.objects.filter(code="2").first(),
                product=CustomerProduct.objects.filter(slug="Slug1").first(),
                total_quantity=11.1,
                remaining_quantity=11.2,
                price_per_unit=11,
                quantity_unit="TON",
                currency="VND",
                weight=10.2,
                weight_unit="g",
            ),
            CustomerContractProduct(
                contract=CustomerContract.objects.filter(code="2").first(),
                product=CustomerProduct.objects.filter(slug="Slug2").first(),
                total_quantity=12.1,
                remaining_quantity=12.2,
                price_per_unit=12,
                quantity_unit="TON",
                currency="$$",
                weight=11.2,
                weight_unit="Kg",
            ),
            CustomerContractProduct(
                contract=CustomerContract.objects.filter(code="3").first(),
                product=CustomerProduct.objects.filter(slug="Slug3").first(),
                total_quantity=13.1,
                remaining_quantity=13.2,
                price_per_unit=13,
                quantity_unit="TON",
                currency="USD",
                weight=12.2,
                weight_unit="Kg",
            ),
            CustomerContractProduct(
                contract=CustomerContract.objects.filter(code="3").first(),
                product=CustomerProduct.objects.filter(slug="Slug4").first(),
                total_quantity=14.1,
                remaining_quantity=14.2,
                price_per_unit=14,
                quantity_unit="TON",
                currency="USD",
                weight=14.2,
                weight_unit="Kg",
            ),
        ]
    )


@pytest.fixture
def scgp_customer_product_variants(db, scgp_customer_products_for_search):
    return CustomerProductVariant.objects.bulk_create(
        [
            CustomerProductVariant(
                name="Variant P1 1",
                slug="Variant_p1_1",
                product=scgp_customer_products_for_search[0],
            ),
            CustomerProductVariant(
                name="Variant P1 2",
                slug="Variant_p1_2",
                product=scgp_customer_products_for_search[0],
            ),
            CustomerProductVariant(
                name="Variant P1 3",
                slug="Variant_p1_3",
                product=scgp_customer_products_for_search[0],
            ),
            CustomerProductVariant(
                name="Variant P2 1",
                slug="Variant_p2_1",
                product=scgp_customer_products_for_search[1],
            ),
            CustomerProductVariant(
                name="Variant P2 2",
                slug="Variant_p2_2",
                product=scgp_customer_products_for_search[1],
            ),
            CustomerProductVariant(
                name="Variant P2 3",
                slug="Variant_p2_3",
                product=scgp_customer_products_for_search[1],
            ),
            CustomerProductVariant(
                name="Variant P2 4",
                slug="Variant_p2_4",
                product=scgp_customer_products_for_search[1],
            ),
        ]
    )


@pytest.fixture
def scgp_customer_contract_products(
    db,
    scgp_customer_contracts,
    scgp_customer_products_for_search,
):
    return CustomerContractProduct.objects.bulk_create(
        [
            CustomerContractProduct(
                contract=scgp_customer_contracts[0],
                product=scgp_customer_products_for_search[0],
                total_quantity=10000,
                remaining_quantity=9000,
                price_per_unit=500,
                quantity_unit=10,
                currency="xx1",
                weight=500,
                weight_unit=1,
            ),
            CustomerContractProduct(
                contract=scgp_customer_contracts[1],
                product=scgp_customer_products_for_search[1],
                total_quantity=10000,
                remaining_quantity=9000,
                price_per_unit=500,
                quantity_unit=10,
                currency="xx2",
                weight=500,
                weight_unit=1,
            ),
        ]
    )


@pytest.fixture
def scgp_customer_carts(db, customers_for_search, scgp_customer_contracts):
    return CustomerCart.objects.bulk_create(
        [
            CustomerCart(
                contract=scgp_customer_contracts[0],
                created_by=customers_for_search[0],
            ),
            CustomerCart(
                contract=scgp_customer_contracts[1],
                created_by=customers_for_search[0],
            ),
            CustomerCart(
                contract=scgp_customer_contracts[2],
                created_by=customers_for_search[0],
            ),
        ]
    )


@pytest.fixture
def scgp_customer_cart_items(
    db,
    scgp_customer_carts,
    scgp_customer_product_variants,
    scgp_customer_contract_products,
):
    return CustomerCartItem.objects.bulk_create(
        [
            CustomerCartItem(
                quantity=100,
                cart=scgp_customer_carts[0],
                variant=scgp_customer_product_variants[0],
                contract_product=scgp_customer_contract_products[0],
            ),
            CustomerCartItem(
                quantity=100,
                cart=scgp_customer_carts[0],
                variant=scgp_customer_product_variants[1],
                contract_product=scgp_customer_contract_products[0],
            ),
            CustomerCartItem(
                quantity=100,
                cart=scgp_customer_carts[0],
                variant=scgp_customer_product_variants[2],
                contract_product=scgp_customer_contract_products[0],
            ),
            CustomerCartItem(
                quantity=100,
                cart=scgp_customer_carts[1],
                variant=scgp_customer_product_variants[3],
                contract_product=scgp_customer_contract_products[1],
            ),
            CustomerCartItem(
                quantity=100,
                cart=scgp_customer_carts[1],
                variant=scgp_customer_product_variants[4],
                contract_product=scgp_customer_contract_products[1],
            ),
            CustomerCartItem(
                quantity=100,
                cart=scgp_customer_carts[1],
                variant=scgp_customer_product_variants[5],
                contract_product=scgp_customer_contract_products[1],
            ),
            CustomerCartItem(
                quantity=200,
                cart=scgp_customer_carts[2],
                variant=scgp_customer_product_variants[5],
                contract_product=scgp_customer_contract_products[1],
            ),
            CustomerCartItem(
                quantity=10,
                cart=scgp_customer_carts[2],
                variant=scgp_customer_product_variants[5],
                contract_product=scgp_customer_contract_products[1],
            ),
            CustomerCartItem(
                quantity=100,
                cart=scgp_customer_carts[2],
                variant=scgp_customer_product_variants[5],
                contract_product=scgp_customer_contract_products[1],
            ),
        ]
    )


@pytest.fixture
def scgp_customer_orders(db, customers_for_search, scgp_customer_contracts):
    return CustomerOrder.objects.bulk_create(
        [
            CustomerOrder(
                contract=scgp_customer_contracts[0],
                total_price=300,
                total_price_inc_tax=321,
                tax_amount=21,
                status=ScgpCustomerOrderStatus.DRAFT.value,
                created_by=customers_for_search[0],
                created_at=create_date_for_test(-7),
                updated_at=create_date_for_test(-7),
            ),
            CustomerOrder(
                contract=scgp_customer_contracts[0],
                total_price=150,
                total_price_inc_tax=160.5,
                tax_amount=10.5,
                status=ScgpCustomerOrderStatus.CONFIRMED.value,
                order_date=create_date_for_test(-7),
                order_no="1245",
                request_delivery_date=create_date_for_test(7),
                ship_to="128 Phung Hung",
                bill_to="so 1 Tran Vy",
                unloading_point="some thing",
                remark_for_invoice="no thing",
                remark_for_logistic="test remark for logistic",
                created_by=customers_for_search[1],
                created_at=create_date_for_test(-7),
                updated_at=create_date_for_test(-7),
            ),
            CustomerOrder(
                contract=scgp_customer_contracts[0],
                total_price=150,
                total_price_inc_tax=160.5,
                tax_amount=10.5,
                status=ScgpCustomerOrderStatus.DRAFT.value,
                order_date=create_date_for_test(-7),
                order_no="1245",
                request_delivery_date=create_date_for_test(7),
                ship_to="128 Phung Hung",
                bill_to="so 1 Tran Vy",
                unloading_point="some thing",
                remark_for_invoice="no thing",
                remark_for_logistic="test remark for logistic",
                created_by=customers_for_search[2],
                created_at=create_date_for_test(-7),
                updated_at=create_date_for_test(-7),
            ),
            CustomerOrder(
                contract=scgp_customer_contracts[2],
                total_price=150,
                total_price_inc_tax=160.5,
                tax_amount=10.5,
                status=ScgpCustomerOrderStatus.DRAFT.value,
                order_date=create_date_for_test(-7),
                order_no="1245",
                request_delivery_date=create_date_for_test(7),
                ship_to="128 Phung Hung",
                bill_to="so 1 Tran Vy",
                unloading_point="some thing",
                remark_for_invoice="no thing",
                remark_for_logistic="test remark for logistic",
                created_by=customers_for_search[2],
                created_at=create_date_for_test(-7),
                updated_at=create_date_for_test(-7),
            ),
        ]
    )


@pytest.fixture
def scgp_customer_order_lines(
    db,
    scgp_customer_cart_items,
    scgp_customer_orders,
    scgp_customer_contract_products,
    scgp_customer_product_variants,
):
    return CustomerOrderLine.objects.bulk_create(
        [
            CustomerOrderLine(
                order=scgp_customer_orders[0],
                contract_product=scgp_customer_contract_products[0],
                variant=scgp_customer_product_variants[0],
                quantity=10,
                quantity_unit="TON",
                weight_per_unit=9.2,
                total_weight=92,
                price_per_unit=10,
                total_price=100,
                request_delivery_date=create_date_for_test(-2),
            ),
            CustomerOrderLine(
                order=scgp_customer_orders[0],
                contract_product=scgp_customer_contract_products[0],
                variant=scgp_customer_product_variants[1],
                quantity=20,
                quantity_unit="can",
                weight_per_unit=9.2,
                total_weight=184,
                price_per_unit=10,
                total_price=200,
                request_delivery_date=create_date_for_test(-2),
            ),
            CustomerOrderLine(
                order=scgp_customer_orders[1],
                contract_product=scgp_customer_contract_products[0],
                variant=scgp_customer_product_variants[1],
                quantity=15,
                quantity_unit="can",
                weight_per_unit=9.2,
                total_weight=138,
                price_per_unit=10,
                total_price=150,
                request_delivery_date=create_date_for_test(-2),
            ),
            CustomerOrderLine(
                order=scgp_customer_orders[3],
                contract_product=scgp_customer_contract_products[0],
                variant=scgp_customer_product_variants[0],
                quantity=10,
                quantity_unit="TON",
                weight_per_unit=9.2,
                total_weight=92,
                price_per_unit=10,
                total_price=100,
                request_delivery_date=create_date_for_test(-2),
                cart_item=scgp_customer_cart_items[6],
            ),
            CustomerOrderLine(
                order=scgp_customer_orders[3],
                contract_product=scgp_customer_contract_products[0],
                variant=scgp_customer_product_variants[0],
                quantity=100,
                quantity_unit="TON",
                weight_per_unit=9.2,
                total_weight=92,
                price_per_unit=10,
                total_price=100,
                request_delivery_date=create_date_for_test(-2),
                cart_item=scgp_customer_cart_items[7],
            ),
            CustomerOrderLine(
                order=scgp_customer_orders[3],
                contract_product=scgp_customer_contract_products[0],
                variant=scgp_customer_product_variants[0],
                quantity=100,
                quantity_unit="TON",
                weight_per_unit=9.2,
                total_weight=92,
                price_per_unit=10,
                total_price=100,
                request_delivery_date=create_date_for_test(-2),
                cart_item=scgp_customer_cart_items[8],
            ),
        ]
    )


@pytest.fixture
def scgp_customer_user_api_client(customers_for_search):
    return ApiClient(user=customers_for_search[0])
