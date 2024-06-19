import pytest

from saleor.account.models import Address, User


@pytest.fixture
def scg_customers_account_address(db):
    return Address.objects.bulk_create(
        [
            Address(
                first_name="John",
                last_name="Allen",
                street_address_1="8647 Wiggins Garden Apt. 481",
                street_address_2="8648 Wiggins Garden Apt. 42",
                city="South Tylermouth",
                postal_code="59506",
                country="US",
                country_area="MT",
            ),
            Address(
                first_name="Kevin",
                last_name="Durant",
                street_address_1="9999 Wiggins Garden Apt. 481",
                street_address_2="6666 Wiggins Garden Apt. 42",
                city="Boston",
                postal_code="59896",
                country="US",
                country_area="MT",
            ),
            Address(
                first_name="Steph",
                last_name="Curry",
                street_address_1="9991 Wiggins Garden Apt. 500",
                street_address_2="7878 Wiggins Garden Apt. 42",
                city="New York",
                postal_code="59506",
                country="US",
                country_area="MT",
            ),
        ]
    )


@pytest.fixture
def scg_customers_for_search(db, scg_customers_account_address):
    customers = User.objects.bulk_create(
        [
            User(
                first_name="John",
                last_name="Allen",
                email="allen@example.com",
                is_staff=False,
                is_active=True,
                default_billing_address=Address.objects.filter(
                    street_address_1="8647 Wiggins Garden Apt. 481"
                ).first(),
            ),
            User(
                first_name="Kevin",
                last_name="Durant",
                email="kevin@example.com",
                is_staff=False,
                is_active=True,
                default_billing_address=Address.objects.filter(
                    street_address_1="9999 Wiggins Garden Apt. 481"
                ).first(),
            ),
            User(
                first_name="Steph",
                last_name="Curry",
                email="steph@example.com",
                is_staff=False,
                is_active=True,
                default_billing_address=Address.objects.filter(
                    street_address_1="9991 Wiggins Garden Apt. 500"
                ).first(),
            ),
        ]
    )

    for user in customers:
        user.addresses.set(scg_customers_account_address)
    return customers
