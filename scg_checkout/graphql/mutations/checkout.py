import graphene

from saleor.core.exceptions import PermissionDenied
from saleor.graphql.core.mutations import ModelMutation, BaseMutation
from saleor.graphql.core.scalars import PositiveDecimal
from saleor.graphql.core.types import NonNullList
from sap_migration import models as migration_model
from scg_checkout.contract_create_checkout import (
    contract_checkout_lines_delete,
    contract_create_checkout,
    contract_update_checkout,
    delete_order_line_newly_added_in_database, resolve_check_contract_expired_complete_invalid,
    delete_and_sync_order_line_with_es_26,
)

from ..contract_checkout_error import ContractCheckoutError
from ..types import ContractCheckout


class ContractCheckoutLineInput(graphene.InputObjectType):
    product_id = graphene.ID(required=True, description="ID of the contract.")
    quantity = graphene.Float(required=True, description="The number of items purchased.")
    contract_material_id = graphene.ID(required=False, description="ID of the contract material")
    variant_id = graphene.ID(required=False, description="ID of the product variant.")
    price = PositiveDecimal(
        required=False,
        description="price positive",
    )


class ContractCheckoutCreateInput(graphene.InputObjectType):
    contract_id = graphene.ID(required=True, description="ID of the contract.")
    user_id = graphene.ID(required=True, description="ID of the contract.")
    lines = NonNullList(
        ContractCheckoutLineInput,
        description=(
            "A list of checkout lines, each containing information about "
            "an item in the checkout."
        ),
        required=True,
    )


class ContractCheckoutCreate(ModelMutation):
    class Arguments:
        input = ContractCheckoutCreateInput(
            required=True, description="Fields required to create checkout."
        )

    class Meta:
        description = "Create a new checkout."
        model = migration_model.Cart
        object_type = ContractCheckout
        return_field_name = "checkout"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        result = contract_create_checkout(data["input"], info.context.user)
        return cls.success_response(result)


class ContractCheckoutLineUpdateInput(graphene.InputObjectType):
    id = graphene.ID(required=True, description="ID of the contract.")
    product_id = graphene.ID(required=True, description="ID of the contract.")
    quantity = graphene.Int(required=True, description="The number of items purchased.")
    variant_id = graphene.ID(required=True, description="ID of the product variant.")
    price = PositiveDecimal(
        required=False,
        description="price positive",
    )
    selected = graphene.Boolean(required=True, description="ID of the product variant.")


class ContractCheckoutUpdateInput(graphene.InputObjectType):
    contract_id = graphene.ID(required=False, description="ID of the contract.")
    user_id = graphene.ID(required=False, description="ID of the contract.")
    lines = NonNullList(
        ContractCheckoutLineUpdateInput,
        description=(
            "A list of checkout lines, each containing information about "
            "an item in the checkout."
        ),
        required=True,
    )


class ContractCheckoutUpdate(ModelMutation):
    class Meta:
        description = "Create a new checkout."
        model = migration_model.Cart
        object_type = ContractCheckout
        return_field_name = "checkout"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    class Arguments:
        id = graphene.ID(description="ID of a warehouse to update.", required=True)
        input = ContractCheckoutUpdateInput(
            required=True, description="Fields required to create checkout."
        )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cart = migration_model.Cart.objects.filter(
            id=data["id"], created_by=info.context.user
        ).first()
        if not cart:
            raise PermissionDenied("Cannot update shopping cart of other user")

        result = contract_update_checkout(data)
        return cls.success_response(result)


class ContractCheckoutLinesDeleteDelete(ModelMutation):
    status = graphene.String()

    class Meta:
        description = "Delete checkout lines."
        model = migration_model.Cart
        object_type = ContractCheckout
        return_field_name = "checkout"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    class Arguments:
        checkout_line_ids = graphene.List(
            graphene.ID, description="ID of checkout lines to delete", required=True
        )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        lines = migration_model.CartLines.objects.filter(
            id__in=data["checkout_line_ids"])
        if not lines:
            raise PermissionDenied("Don't have any checkout lines")

        contract_checkout_lines_delete(data)
        return cls(status=True)


class DeleteNewlyAddedOrderLineDelete(ModelMutation):
    status = graphene.String()

    class Meta:
        description = "Delete checkout lines."
        model = migration_model.Cart
        object_type = ContractCheckout
        return_field_name = "checkout"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    class Arguments:
        list_item_no = graphene.List(graphene.String, description="List item no order line")
        so_no = graphene.String()

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        list_item_no = data["list_item_no"] or []
        so_no = data["so_no"]
        status = delete_order_line_newly_added_in_database(so_no, list_item_no)
        return cls(status=status)


class DeleteAndSyncOrderLine(ModelMutation):
    status = graphene.String()

    class Meta:
        description = "Delete checkout lines."
        model = migration_model.Cart
        object_type = ContractCheckout
        return_field_name = "checkout"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    class Arguments:
        # list_item_no = graphene.List(graphene.String, description="List item no order line")
        so_no = graphene.String()

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        so_no = data["so_no"]
        status = delete_and_sync_order_line_with_es_26(so_no)
        return cls(status=status)


class CheckContractExpiredCompleteInvalid(BaseMutation):
    is_invalid = graphene.Boolean(description="Contract is invalid or not")

    class Arguments:
        contract_no = graphene.String(description="Code of contract", required=True)

    class Meta:
        description = "Recheck if Contract Expired/Complete/Invalid"
        error_type_class = ContractCheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        contract_no = data["contract_no"]
        result = resolve_check_contract_expired_complete_invalid(contract_no)
        return cls(is_invalid=result)
