import random

import pytest

from saleor.account.models import User
from saleor.graphql.tests.fixtures import ApiClient
from scg_checkout.graphql.enums import AlternativeMaterialTypes, ScgOrderStatus
from scg_checkout.models import (
    AlternativeMaterial,
    AlternativeMaterialOs,
    BusinessUnit,
    Company,
    Contract,
    ContractProduct,
    DistributionChannel,
    Division,
    Product,
    ProductVariant,
    SalesGroup,
    SalesOffice,
    SalesOrganization,
    TempCheckout,
    TempCheckoutLine,
    TempOrder,
    TempOrderLine,
)


@pytest.fixture()
def data():
    class Data:
        second_field = "test"

    return Data()


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
def scgp_customer_api_client(customers_for_search):
    return ApiClient(user=customers_for_search[0])


@pytest.fixture
def business_units_for_search(db):
    return BusinessUnit.objects.bulk_create(
        [
            BusinessUnit(name="PP"),
            BusinessUnit(name="FB"),
            BusinessUnit(name="CIP"),
        ]
    )


@pytest.fixture
def companies_for_search(db, business_units_for_search):
    return Company.objects.bulk_create(
        [
            Company(
                name="Siam Kraft",
                business_unit=BusinessUnit.objects.filter(name="PP").first(),
            ),
            Company(
                name="Thai Cane",
                business_unit=BusinessUnit.objects.filter(name="FB").first(),
            ),
            Company(
                name="Feast",
                business_unit=BusinessUnit.objects.filter(name="PP").first(),
            ),
            Company(
                name="Idea",
                business_unit=BusinessUnit.objects.filter(name="CIP").first(),
            ),
        ]
    )


@pytest.fixture
def contracts_for_search(db, companies_for_search, customers_for_search):
    return Contract.objects.bulk_create(
        [
            Contract(
                company=Company.objects.filter(name="Siam Kraft").first(),
                customer=User.objects.get(email="allen@example.com"),
                project_name="TCP TCKK Contact 24/04/2022 - 23/05/2022",
                start_date="2022-02-01",
                end_date="2022-04-01",
                payment_term="30 day credit",
            ),
            Contract(
                company=Company.objects.filter(name="Thai Cane").first(),
                customer=User.objects.get(email="zordon01@example.com"),
                project_name="OS_COR100M_Mar_TCKK",
                start_date="2022-02-02",
                end_date="2022-04-02",
                payment_term="40 day credit",
            ),
            Contract(
                company=Company.objects.filter(name="Thai Cane").first(),
                customer=User.objects.get(email="allen@example.com"),
                project_name="TCKK STD. 10/3/2022 - 09/4/2022",
                start_date="2022-02-03",
                end_date="2022-04-03",
                payment_term="50 day credit",
            ),
            Contract(
                company=Company.objects.filter(name="Feast").first(),
                customer=User.objects.get(email="allen@example.com"),
                project_name="TCP OS STD. opt Contact 20/06/2022 - 18/07/2022",
                start_date="2022-02-04",
                end_date="2022-04-04",
                payment_term="60 day credit",
            ),
            Contract(
                company=Company.objects.filter(name="Feast").first(),
                customer=User.objects.get(email="zordon01@example.com"),
                project_name="LOREM IPSUM_COR120M_Jan-Sep - 2023",
                start_date="2022-02-05",
                end_date="2022-04-05",
                payment_term="70 day credit",
            ),
        ]
    )


@pytest.fixture
def scg_checkout_products(db):
    return Product.objects.bulk_create(
        [
            Product(
                name="CA-090D",
                sales_unit="TON",
                code="COD1",
                dia="DIA1",
                grade_gram="GRADE-GRAM",
            ),
            Product(
                name="KA-ConfiDenz230D",
                sales_unit="TON",
                code="COD2",
                dia="DIA2",
                grade_gram="GRADE-GRAM",
            ),
            Product(
                name="CS - SuperFlute125D",
                sales_unit="TON",
                code="COD3",
                dia="DIA3",
                grade_gram="GRADE-GRAM",
            ),
            Product(
                name="CA - 105D",
                sales_unit="TON",
                code="COD4",
                dia="DIA4",
                grade_gram="GRADE-GRAM",
            ),
            Product(name="CA - 187D", sales_unit="TON", code="COD5", dia="DIA5"),
        ]
    )


@pytest.fixture
def contract_products_for_search(db, contracts_for_search, scg_checkout_products):
    return ContractProduct.objects.bulk_create(
        [
            ContractProduct(
                contract=Contract.objects.filter(
                    project_name="TCP TCKK Contact 24/04/2022 - 23/05/2022"
                ).first(),
                product=Product.objects.filter(name="CA-090D").first(),
                total=12000,
                remain=8000,
                price=2300,
            ),
            ContractProduct(
                contract=Contract.objects.filter(
                    project_name="TCP TCKK Contact 24/04/2022 - 23/05/2022"
                ).first(),
                product=Product.objects.filter(name="KA-ConfiDenz230D").first(),
                total=13000,
                remain=9000,
                price=2400,
            ),
            ContractProduct(
                contract=Contract.objects.filter(
                    project_name="TCP TCKK Contact 24/04/2022 - 23/05/2022"
                ).first(),
                product=Product.objects.filter(name="CS - SuperFlute125D").first(),
                total=14000,
                remain=7500,
                price=2500,
            ),
            ContractProduct(
                contract=Contract.objects.filter(
                    project_name="TCP TCKK Contact 24/04/2022 - 23/05/2022"
                ).first(),
                product=Product.objects.filter(name="CA - 105D").first(),
                total=12000,
                remain=7500,
                price=2300,
            ),
            ContractProduct(
                contract=Contract.objects.filter(
                    project_name="TCP TCKK Contact 24/04/2022 - 23/05/2022"
                ).first(),
                product=Product.objects.filter(name="CA - 187D").first(),
                total=12000,
                remain=6000,
                price=2600,
            ),
            ContractProduct(
                contract=Contract.objects.filter(
                    project_name="TCKK STD. 10/3/2022 - 09/4/2022"
                ).first(),
                product=Product.objects.filter(name="CA - 105D").first(),
                total=12000,
                remain=2000,
                price=2300,
            ),
            ContractProduct(
                contract=Contract.objects.filter(
                    project_name="TCKK STD. 10/3/2022 - 09/4/2022"
                ).first(),
                product=Product.objects.filter(name="CA - 187D").first(),
                total=12000,
                remain=2000,
                price=2600,
            ),
        ]
    )


@pytest.fixture
def scg_product_variants(db, scg_checkout_products):
    return ProductVariant.objects.bulk_create(
        [
            ProductVariant(
                name="CA-090D-93 / 36 INCH DIA117N SC Mix50%",
                product=Product.objects.filter(name="CA-090D").first(),
                weight=10,
            ),
            ProductVariant(
                name="Test / 36 INCH DIA117N SC Mix50%",
                product=Product.objects.filter(name="CA-090D").first(),
                weight=50,
            ),
            ProductVariant(
                name="CA-090D-94 / 36 INCH DIA117N SC Mix50%",
                product=Product.objects.filter(name="KA-ConfiDenz230D").first(),
                weight=10,
            ),
            ProductVariant(
                name="CA-090D-95 / 36 INCH DIA117N SC Mix50%",
                product=Product.objects.filter(name="CS - SuperFlute125D").first(),
                weight=10,
            ),
        ]
    )


@pytest.fixture
def scg_checkouts(db, contracts_for_search, customers_for_search):
    return TempCheckout.objects.bulk_create(
        [
            TempCheckout(
                contract=Contract.objects.filter(
                    project_name="TCP TCKK Contact 24/04/2022 - 23/05/2022"
                ).first(),
                user=User.objects.filter(email="allen@example.com").first(),
                created_by=User.objects.filter(email="staff_test@example.com").first(),
            ),
            TempCheckout(
                contract=Contract.objects.filter(
                    project_name="OS_COR100M_Mar_TCKK"
                ).first(),
                user=User.objects.filter(email="zordon01@example.com").first(),
                created_by=User.objects.filter(email="staff_test@example.com").first(),
            ),
            TempCheckout(
                contract=Contract.objects.filter(
                    project_name="TCKK STD. 10/3/2022 - 09/4/2022"
                ).first(),
                user=User.objects.filter(email="leslie@example.com").first(),
                created_by=User.objects.filter(email="staff_test@example.com").first(),
            ),
        ]
    )


@pytest.fixture
def scg_checkout_lines(
    db,
    scg_checkouts,
    scg_product_variants,
    scg_checkout_products,
    contract_products_for_search,
):
    return TempCheckoutLine.objects.bulk_create(
        [
            TempCheckoutLine(
                checkout=TempCheckout.objects.filter(
                    user__email="allen@example.com"
                ).first(),
                product=Product.objects.filter(name="CA-090D").first(),
                variant=ProductVariant.objects.filter(
                    name="CA-090D-93 / 36 INCH DIA117N SC Mix50%"
                ).first(),
                contract_product=ContractProduct.objects.filter(
                    contract__project_name="TCP TCKK Contact 24/04/2022 - 23/05/2022"
                ).first(),
                quantity=12,
                price=10,
            ),
            TempCheckoutLine(
                checkout=TempCheckout.objects.filter(
                    user__email="allen@example.com"
                ).first(),
                product=Product.objects.filter(name="CA-090D").first(),
                variant=ProductVariant.objects.filter(
                    name="Test / 36 INCH DIA117N SC Mix50%"
                ).first(),
                contract_product=ContractProduct.objects.filter(
                    contract__project_name="TCP TCKK Contact 24/04/2022 - 23/05/2022"
                ).first(),
                quantity=20,
                price=10,
            ),
            TempCheckoutLine(
                checkout=TempCheckout.objects.filter(
                    user__email="zordon01@example.com"
                ).first(),
                product=Product.objects.filter(name="KA-ConfiDenz230D").first(),
                variant=ProductVariant.objects.filter(
                    name="CA-090D-94 / 36 INCH DIA117N SC Mix50%"
                ).first(),
                contract_product=ContractProduct.objects.filter(
                    contract__project_name="TCP TCKK Contact 24/04/2022 - 23/05/2022"
                ).first(),
                quantity=12,
                price=10,
            ),
            TempCheckoutLine(
                checkout=TempCheckout.objects.filter(
                    user__email="leslie@example.com"
                ).first(),
                product=Product.objects.filter(name="CS - SuperFlute125D").first(),
                variant=ProductVariant.objects.filter(
                    name="CA-090D-95 / 36 INCH DIA117N SC Mix50%"
                ).first(),
                contract_product=ContractProduct.objects.filter(
                    contract__project_name="TCP TCKK Contact 24/04/2022 - 23/05/2022"
                ).first(),
                quantity=12,
                price=10,
            ),
        ]
    )


@pytest.fixture
def scg_checkout_orders(
    db, customers_for_search, scg_product_variants, scg_checkout_lines
):
    orders = TempOrder.objects.bulk_create(
        [
            TempOrder(
                customer_id=customers_for_search[0].id,
                status=ScgOrderStatus.DRAFT.value,
            ),
            TempOrder(
                customer_id=customers_for_search[1].id,
                status=ScgOrderStatus.DRAFT.value,
            ),
            TempOrder(
                customer_id=customers_for_search[2].id,
                status=ScgOrderStatus.DRAFT.value,
            ),
        ]
    )

    order_lines = TempOrderLine.objects.bulk_create(
        [
            TempOrderLine(
                order_id=orders[0].id,
                product=scg_checkout_lines[0].product,
                variant_id=scg_product_variants[0].id,
                contract_product=scg_checkout_lines[0].contract_product,
                quantity=10,
                net_price=10 * scg_checkout_lines[0].contract_product.price,
                request_date="2021-01-01",
                checkout_line_id=scg_checkout_lines[0].id,
            ),
            TempOrderLine(
                order_id=orders[1].id,
                product=scg_checkout_lines[0].product,
                variant_id=scg_product_variants[0].id,
                contract_product=scg_checkout_lines[0].contract_product,
                quantity=10,
                net_price=10 * scg_checkout_lines[0].contract_product.price,
                request_date="2021-01-01",
                checkout_line_id=scg_checkout_lines[0].id,
            ),
            TempOrderLine(
                order_id=orders[1].id,
                product=scg_checkout_lines[1].product,
                variant_id=scg_product_variants[1].id,
                contract_product=scg_checkout_lines[1].contract_product,
                quantity=10,
                net_price=10 * scg_checkout_lines[1].contract_product.price,
                request_date="2021-01-01",
                checkout_line_id=scg_checkout_lines[1].id,
            ),
            TempOrderLine(
                order_id=orders[0].id,
                product=scg_checkout_lines[0].product,
                variant_id=scg_product_variants[0].id,
                contract_product=scg_checkout_lines[0].contract_product,
                quantity=10,
                net_price=10 * scg_checkout_lines[0].contract_product.price,
                request_date="2021-01-01",
                checkout_line_id=scg_checkout_lines[0].id,
            ),
            TempOrderLine(
                order_id=orders[2].id,
                product=scg_checkout_lines[1].product,
                variant_id=scg_product_variants[1].id,
                contract_product=scg_checkout_lines[1].contract_product,
                quantity=10,
                net_price=10 * scg_checkout_lines[1].contract_product.price,
                request_date="2021-01-01",
                checkout_line_id=scg_checkout_lines[1].id,
            ),
            TempOrderLine(
                order_id=orders[2].id,
                product=scg_checkout_lines[2].product,
                variant_id=scg_product_variants[2].id,
                contract_product=scg_checkout_lines[2].contract_product,
                quantity=10,
                net_price=10 * scg_checkout_lines[2].contract_product.price,
                request_date="2021-01-01",
                checkout_line_id=scg_checkout_lines[2].id,
            ),
        ]
    )
    return orders, order_lines


@pytest.fixture
def scg_checkout_distribution_channel(db):
    return DistributionChannel.objects.bulk_create(
        [
            DistributionChannel(name="1", code="1"),
            DistributionChannel(name="2", code="2"),
            DistributionChannel(name="3", code="3"),
        ]
    )


@pytest.fixture
def scg_checkout_sales_organization(db):
    return SalesOrganization.objects.bulk_create(
        [
            SalesOrganization(name="1", code="1"),
            SalesOrganization(name="2", code="2"),
            SalesOrganization(name="3", code="3"),
        ]
    )


@pytest.fixture
def scg_checkout_division(db):
    return Division.objects.bulk_create(
        [
            Division(name="1", code="1"),
            Division(name="2", code="2"),
            Division(name="3", code="3"),
        ]
    )


@pytest.fixture
def scg_checkout_sales_office(db):
    return SalesOffice.objects.bulk_create(
        [
            SalesOffice(name="1", code="1"),
            SalesOffice(name="2", code="2"),
            SalesOffice(name="3", code="3"),
        ]
    )


@pytest.fixture
def scg_checkout_sales_group(db):
    return SalesGroup.objects.bulk_create(
        [
            SalesGroup(name="1", code="1"),
            SalesGroup(name="2", code="2"),
            SalesGroup(name="3", code="3"),
        ]
    )


@pytest.fixture
def scg_alternative_material(
    db, scg_checkout_sales_organization, scg_sold_tos_data_test, scg_checkout_products
):

    return AlternativeMaterial.objects.bulk_create(
        [
            AlternativeMaterial(
                sales_organization=random.choice(scg_checkout_sales_organization),
                sold_to=random.choice(scg_sold_tos_data_test),
                material_own=product,
                type=random.choice([AlternativeMaterialTypes.MATERIAL.value, None]),
            )
            for product in scg_checkout_products
        ]
    )


@pytest.fixture
def scg_alternative_material_os(db, scg_alternative_material, scg_checkout_products):

    return AlternativeMaterialOs.objects.bulk_create(
        [
            AlternativeMaterialOs(
                alternative_material=random.choice(scg_alternative_material),
                material_os=random.choice(scg_checkout_products),
                priority=x + 1,
            )
            for x in range(1000)
        ]
    )
