import pytest
from django.core.exceptions import FieldError

# from saleor.account.models import User
from saleor.graphql.tests.utils import (  # get_graphql_content,
    assert_graphql_error_with_message,
    get_graphql_content_from_response,
)
from scg_checkout.graphql.helper import get_internal_emails_by_config
from scg_checkout.graphql.implementations.iplan import (
    get_external_emails_by_config,
    get_partner_emails_from_es17_response,
    get_sap_warning_messages,
)

# from scg_checkout.models import TempCheckout, TempCheckoutLine
from scg_checkout.tests.operations import (  # DELETE_CONTRACT_CHECKOUT_LINES,
    CREATE_CONTRACT_CHECKOUT,
    UPDATE_CONTRACT_CHECKOUT,
)
from scgp_user_management.models import EmailConfigurationFeatureChoices

# def test_create_contract_checkout_return_success(
#     staff_api_client,
#     contract_products_for_search,
#     contracts_for_search,
#     customers_for_search,
#     scg_checkout_products,
#     scg_product_variants,
#     scg_checkout_lines,
# ):
#     variables = {
#         "input": {
#             "contractId": contracts_for_search[0].id,
#             "userId": customers_for_search[0].id,
#             "lines": [
#                 {
#                     "productId": scg_checkout_products[0].id,
#                     "quantity": 10,
#                     "variantId": scg_product_variants[0].id,
#                     "price": 10,
#                 }
#             ],
#         }
#     }

#     response = staff_api_client.post_graphql(
#         CREATE_CONTRACT_CHECKOUT,
#         variables,
#     )
#     content = get_graphql_content(response)
#     checkout_line = TempCheckoutLine.objects.filter(checkout_id=1).first()
#     checkout_line_id_response = content["data"]["createContractCheckout"]["checkout"][
#         "lines"
#     ][0].get("id")
#     contract_product_response = content["data"]["createContractCheckout"]["checkout"][
#         "lines"
#     ][0].get("contractProduct")
#     assert checkout_line_id_response == str(checkout_line.id)
#     assert contract_product_response.get("id") == str(checkout_line.contract_product.id)


def test_create_contract_checkout_invalid_field_type(
    staff_api_client,
    contracts_for_search,
    customers_for_search,
    scg_checkout_products,
    scg_product_variants,
    scg_checkout_lines,
):
    variables = {
        "input": {
            "contractId": "string",
            "userId": customers_for_search[0].id,
            "lines": [
                {
                    "productId": scg_checkout_products[0].id,
                    "quantity": 10,
                    "variantId": scg_product_variants[0].id,
                    "price": 10,
                }
            ],
        }
    }

    response = staff_api_client.post_graphql(
        CREATE_CONTRACT_CHECKOUT,
        variables,
    )
    message = "Field 'id' expected a number but got 'string'."
    content = get_graphql_content_from_response(response)
    assert message in content["errors"][0]["message"]


def test_create_contract_checkout_missing_required_field(
    staff_api_client,
    contracts_for_search,
    customers_for_search,
    scg_checkout_products,
    scg_product_variants,
    scg_checkout_lines,
):
    variables = {
        "input": {
            "userId": customers_for_search[0].id,
            "lines": [
                {
                    "productId": scg_checkout_products[0].id,
                    "quantity": 10,
                    "variantId": scg_product_variants[0].id,
                    "price": 10,
                }
            ],
        }
    }

    response = staff_api_client.post_graphql(
        CREATE_CONTRACT_CHECKOUT,
        variables,
    )
    message = 'field "contractId": Expected "ID!", found null.'
    content = get_graphql_content_from_response(response)
    assert message in content["errors"][0]["message"]


def test_create_contract_checkout_invalid_quantity(
    staff_api_client,
    contracts_for_search,
    customers_for_search,
    scg_checkout_products,
    scg_product_variants,
    scg_checkout_lines,
):
    variables = {
        "input": {
            "contractId": contracts_for_search[0].id,
            "userId": customers_for_search[0].id,
            "lines": [
                {
                    "productId": scg_checkout_products[0].id,
                    "quantity": 0,
                    "variantId": scg_product_variants[0].id,
                    "price": 10,
                }
            ],
        }
    }

    response = staff_api_client.post_graphql(
        CREATE_CONTRACT_CHECKOUT,
        variables,
    )
    message = "Unacceptable quantity value 0"
    assert_graphql_error_with_message(response, message)


# def test_update_contract_checkout_return_success(
#     staff_api_client,
#     scg_checkouts,
#     contracts_for_search,
#     customers_for_search,
#     scg_checkout_products,
#     scg_product_variants,
#     scg_checkout_lines,
# ):
#     variables = {
#         "id": scg_checkouts[0].id,
#         "input": {
#             "lines": [
#                 {
#                     "id": scg_checkout_lines[0].id,
#                     "productId": scg_checkout_products[0].id,
#                     "quantity": 10,
#                     "variantId": scg_product_variants[0].id,
#                     "price": 10,
#                     "selected": True,
#                 }
#             ],
#         },
#     }

#     response = staff_api_client.post_graphql(
#         UPDATE_CONTRACT_CHECKOUT,
#         variables,
#     )
#     content = get_graphql_content(response)
#     contract_checkout = content["data"]["updateContractCheckout"]
#     checkout = TempCheckout.objects.filter(id=1).first()
#     assert contract_checkout["checkout"]["id"] == str(checkout.id)
#     assert contract_checkout["checkout"]["contract"]["id"] == str(checkout.contract.id)


def test_update_contract_checkout_invalid_field_type(
    staff_api_client,
    scg_checkouts,
    contracts_for_search,
    customers_for_search,
    scg_checkout_products,
    scg_product_variants,
    scg_checkout_lines,
):
    variables = {
        "id": "string",
        "input": {
            "lines": [
                {
                    "id": scg_checkout_lines[0].id,
                    "productId": scg_checkout_products[0].id,
                    "quantity": 10,
                    "variantId": scg_product_variants[0].id,
                    "price": 10,
                    "selected": True,
                }
            ],
        },
    }

    response = staff_api_client.post_graphql(
        UPDATE_CONTRACT_CHECKOUT,
        variables,
    )
    message = "Field 'id' expected a number but got 'string'."
    assert_graphql_error_with_message(response, message)


def test_update_contract_checkout_missing_required_field(
    staff_api_client,
    scg_checkouts,
    contracts_for_search,
    customers_for_search,
    scg_checkout_products,
    scg_product_variants,
    scg_checkout_lines,
):
    variables = {
        "input": {
            "lines": [
                {
                    "id": scg_checkout_lines[0].id,
                    "productId": scg_checkout_products[0].id,
                    "quantity": 10,
                    "variantId": scg_product_variants[0].id,
                    "price": 10,
                    "selected": True,
                }
            ],
        }
    }

    response = staff_api_client.post_graphql(
        UPDATE_CONTRACT_CHECKOUT,
        variables,
    )
    message = 'Argument "id" of required type ID!'
    content = get_graphql_content_from_response(response)
    assert message in content["errors"][0]["message"]


# def test_delete_contract_checkout_lines_return_success(
#     staff_api_client,
#     scg_checkout_lines,
# ):
#     variables = {
#         "checkoutLineIds": [scg_checkout_lines[0].id, scg_checkout_lines[1].id]
#     }

#     response = staff_api_client.post_graphql(
#         DELETE_CONTRACT_CHECKOUT_LINES,
#         variables,
#     )

#     content = get_graphql_content(response)
#     contract_checkout_lines = content["data"]["deleteContractCheckoutLines"]

#     assert contract_checkout_lines["status"] == "true"


# def test_delete_contract_checkout_lines_error_id(
#     staff_api_client,
#     scg_checkout_lines,
# ):
#     variables = {"checkoutLineIds": [111]}

#     response = staff_api_client.post_graphql(
#         DELETE_CONTRACT_CHECKOUT_LINES,
#         variables,
#     )

#     message = "Checkout lines do not exist or belong to another user"
#     assert_graphql_error_with_message(response, message)


# def test_concat_variant_id_and_contract_product_id(scg_checkout_lines):
#     variant_id = scg_checkout_lines[0].variant_id
#     contract_product_id = scg_checkout_lines[0].contract_product_id
#     assert (
#         concat_variant_id_and_contract_product_id([variant_id, contract_product_id])
#         == "1_1"
#     )


# def test_concat_variant_id_and_contract_product_id_invalid_input(scg_checkout_lines):
#     variant_id = []
#     contract_product_id = scg_checkout_lines[0].contract_product_id
#     assert (
#         concat_variant_id_and_contract_product_id([variant_id, contract_product_id])
#         == "[]_1"
#     )


# def test_get_checkout_line_objects(scg_checkout_lines):
#     data = get_checkout_line_objects(scg_checkout_lines[0].id)
#     result = {
#         "1_1": {"id": 1, "quantity": 12, "variant_id": 1, "contract_product_id": 1},
#         "2_1": {"id": 2, "quantity": 20, "variant_id": 2, "contract_product_id": 1},
#     }
#     assert data == result


# @mock.patch("scg_checkout.contract_create_checkout.create_or_update_checkout_lines")
# def test_contract_create_checkout(
#     mock_checkout_lines,
#     staff_api_client,
#     contracts_for_search,
#     contract_products_for_search,
#     scg_checkout_lines,
#     scg_checkout_products,
#     scg_product_variants,
#     scg_checkouts,
#     customers_for_search,
# ):
#     checkout_lines = [
#         {
#             "product_id": scg_checkout_products[0].id,
#             "quantity": 10,
#             "variant_id": scg_product_variants[0].id,
#             "price": 10,
#         }
#     ]
#     params = {
#         "contract_id": contracts_for_search[0].id,
#         "user_id": customers_for_search[0].id,
#         "lines": checkout_lines,
#     }
#     create_by = User.objects.filter(email="staff_test@example.com").first()
#     checkout = contract_create_checkout(params, create_by)

#     mock_checkout_lines.assert_called_once_with(
#         checkout_lines, checkout.id, contracts_for_search[0].id
#     )

#     assert checkout.id == scg_checkouts[0].id


# def test_get_partner_emails_from_es17_response(
#     sap_master_data_sold_to_partner, es17_response
# ):
#     partner_emails = get_partner_emails_from_es17_response(es17_response)
#     assert set(partner_emails) == {"0000000001@email.com", "0000000002@email.com"}


@pytest.mark.django_db
def test_get_external_emails_by_config_with_valid_data(
    scgp_user_email_configuration_external,
):
    mail_to, cc_to = get_external_emails_by_config("FeatureA", "001", "GroupA")
    assert mail_to == ["mailtoA1@example.com", "mailtoA2@example.com"]
    assert cc_to == ["cctoA1@example.com"]

    mail_to, cc_to = get_external_emails_by_config("FeAtUrEb", "2", "GrOuPb")
    assert mail_to == ["mailtoB1@example.com"]
    assert cc_to == ["cctoB1@example.com", "cctoB2@example.com"]

    mail_to, cc_to = get_external_emails_by_config("FeatureE", "0005", None)
    assert mail_to == ["mailtoE1@example.com"]
    assert cc_to == ["cctoE1@example.com"]

    mail_to, cc_to = get_external_emails_by_config("FeatureF", "0006", None)
    assert mail_to == ["mailtoF1@example.com"]
    assert cc_to == ["cctoF1@example.com"]

    mail_to, cc_to = get_external_emails_by_config("FeatureG", "0007", "GroupG")
    assert mail_to == []
    assert cc_to == []


@pytest.mark.django_db
def test_get_external_emails_by_config_with_invalid_data(
    scgp_user_email_configuration_external,
):
    mail_to, cc_to = get_external_emails_by_config("FeatureA", "002", "GroupB")
    assert mail_to == []
    assert cc_to == []


@pytest.mark.django_db
def test_get_external_emails_by_config_with_missing_data(
    scgp_user_email_configuration_external,
):
    mail_to, cc_to = get_external_emails_by_config("FeatureC", "003", "GroupC")
    assert mail_to == []
    assert cc_to == ["cctoC1@example.com", "cctoC2@example.com"]

    mail_to, cc_to = get_external_emails_by_config("FeAtUrEd", "4", "GrOuPd")
    assert mail_to == ["mailtoD1@example.com"]
    assert cc_to == []


def test_get_partner_emails_from_es17_response(
    sap_master_data_sold_to_partner, es17_response
):
    partner_emails = get_partner_emails_from_es17_response(es17_response)
    assert set(partner_emails) == {"0000000001@email.com", "0000000002@email.com"}


@pytest.mark.django_db
def test_get_internal_emails_by_config_with_valid_data(
    scgp_users_email_internal_mapping,
):
    # Create Order: Both Sale Org & Product group defined
    mails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.CREATE_ORDER, "0001", "p01", ["bu1"]
    )
    assert set(mails) == {"mailto1@example"}

    # Pending Order: Both Sale Org & Product group defined
    mails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.PENDING_ORDER, "0001", "P01", ["bu4"]
    )
    assert set(mails) == {"mailto4@example"}

    # EO_UPLOAD : Both Sale Org and product group defined
    mails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.EO_UPLOAD, "0002", "P02", ["bu5"]
    )
    assert set(mails) == {"mailto5.1@example", "mailto5.2@example"}

    # EO_UPLOAD : Both Sale Org and product group defined
    # have specific mapping and also All Mappings
    mails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.EO_UPLOAD, "0001", "P02", ["pp"]
    )
    assert set(mails) == {
        "mailto9@example",
        "mailto10@example",
        "mailto11@example",
        "mailto12@example",
    }

    # Create Order: Both Sale Org & Product group defined
    # NOTE: as couldn't find specific mapping consider All mapping
    mails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.CREATE_ORDER, "0007", "P02", ["bu7"]
    )
    assert set(mails) == {"mailto7@example"}

    # PO Upload:  Sale Org Defined & product group Undefined
    mails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.PO_UPLOAD, "0004", "", ["bu2"]
    )
    assert set(mails) == {"mailto2@example"}

    # CREATE_ORDER : Sale Org Undefined and product group defined
    mails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.CREATE_ORDER, "", "p03", ["bu8"]
    )
    assert set(mails) == {"mailto8@example"}

    # ORDER_CONFIRMATION : Both Sale Org and product group Undefined
    mails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.ORDER_CONFIRMATION, "", "", ["bu3"]
    )
    assert set(mails) == {"mailto3@example"}

    # empty case
    mails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.ORDER_CONFIRMATION, "0003", "p03", []
    )
    assert mails == []


@pytest.mark.django_db
def test_get_internal_emails_by_config_with_invalid_data(
    scgp_users_email_internal_mapping,
):
    with pytest.raises(FieldError):
        get_internal_emails_by_config("", "0003", "0030")

    mails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.PO_UPLOAD, "001", "", []
    )
    assert mails == []

    mails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.CREATE_ORDER, "", "", []
    )
    assert mails == []


def test_get_warning_messages_from_sap_response(es17_response_credit_status):
    assert get_sap_warning_messages(es17_response_credit_status[0]) == []
    assert get_sap_warning_messages(es17_response_credit_status[1]) == [
        {
            "source": "sap",
            "order": "0410276010",
            "message": "Credit check was executed, document not OK",
        }
    ]
    assert get_sap_warning_messages(es17_response_credit_status[2]) == []
