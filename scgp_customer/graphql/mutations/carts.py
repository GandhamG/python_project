import graphene
from django.db.models import Count
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from saleor.graphql.core.mutations import ModelMutation
from saleor.graphql.core.scalars import PositiveDecimal
from saleor.graphql.core.types import NonNullList
from scgp_customer.implementations.carts import (
    customer_create_cart,
    update_cart,
    update_customer_cart_line_quantity
)
from scgp_customer.graphql.validators import validate_positive_decimal, validate_quantity

from scgp_customer import models
from scgp_customer.graphql.types import (
    CustomerCart,
    CustomerCartLines
)
from scgp_customer.graphql.scgp_customer_error import ScgpCustomerError
from sap_migration import models as sap_migration_models


class CartItemsDelete(ModelMutation):
    status = graphene.String()

    class Meta:
        description = "Delete customer cart items."
        model = sap_migration_models.Cart
        object_type = CustomerCart
        return_field_name = "cart"
        error_type_class = ScgpCustomerError
        error_type_field = "customer_cart_errors"

    class Arguments:
        cart_item_ids = graphene.List(
            graphene.ID, description="ID of cart times to delete", required=True
        )

    @classmethod
    @transaction.atomic
    def _cart_items_delete(cls, items):
        try:
            cart_items = sap_migration_models.CartLines.objects.filter(
                pk__in=items.get("cart_item_ids")
            )
            cart_id = cart_items[0].cart_id
            cart_items.delete()
            sap_migration_models.Cart.objects.filter(id=cart_id).annotate(
                num_cart_items=Count("cartlines")
            ).filter(num_cart_items=0).delete()

            return cart_id
        except Exception as e:
            transaction.set_rollback(True)
            raise ImproperlyConfigured(e)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        lines = sap_migration_models.CartLines.objects.filter(
            id__in=data["cart_item_ids"],
            cart__created_by=info.context.user,
        )
        if not lines:
            raise ValidationError("Cart items do not exist or belong to another user")

        cls._cart_items_delete(data)
        return cls(status=True)


class CustomerCartItemInput(graphene.InputObjectType):
    product_id = graphene.ID(required=True, description="ID of the customer product.")
    quantity = graphene.Float(required=True)
    variant_id = graphene.ID(required=False, description="ID of the customer product variant.")
    contract_material_id = graphene.ID(required=False, description="ID of the contract material id.")

class CustomerCartLineQuantityInput(graphene.InputObjectType): 
    id = graphene.ID(required=True, description="ID of the cart line.")
    quantity = graphene.Float(required=True)
    material_variant_id = graphene.ID(required=False)

class CustomerCartCreateInput(graphene.InputObjectType):
    customer_id = graphene.ID(required=True, description="ID of the customer.")
    customer_contract_id = graphene.ID(required=True, description="ID of the customer contract.")
    sold_to_id = graphene.ID(required=True, description="ID of the sold to.")
    lines = NonNullList(
        CustomerCartItemInput,
        description=(
            "A list of cart items, each containing information about "
            "an item in the cart."
        ),
        required=True,
    )


class CustomerCartCreate(ModelMutation):
    class Arguments:
        input = CustomerCartCreateInput(
            required=True, description="Fields required to create cart."
        )

    class Meta:
        description = "Create a new cart."
        model = sap_migration_models.Cart
        object_type = CustomerCart
        return_field_name = "cart"
        error_type_class = ScgpCustomerError
        error_type_field = "cart_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        lines = data["input"]["lines"]
        for line in lines:
            quantity = float(line["quantity"])
            validate_positive_decimal(quantity)
        result = customer_create_cart(data["input"], info.context.user)
        return cls.success_response(result)


class CustomerCartUpdateInput(graphene.InputObjectType):
    lines = NonNullList(
        CustomerCartItemInput,
        description=(
            "A list of cart items, each containing information about "
            "an item in the cart."
        ),
        required=True,
    )

class CustomerCartLinesUpdateQuantityInput(graphene.InputObjectType):
    lines = NonNullList(
        CustomerCartLineQuantityInput,
        description=(
            "A list of cart lines, each containing information about "
            "an item in the cart."
        ),
        required=True,
    )


class CustomerCartUpdate(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of a cart to update.", required=True)
        input = CustomerCartUpdateInput(required=True, description="Fields required to update cart.")

    class Meta:
        description = "Update cart."
        model = models.CustomerCart
        object_type = CustomerCart
        return_field_name = "cart"
        error_type_class = ScgpCustomerError
        error_type_field = "cart_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        validate_quantity(data)
        result = update_cart(data["id"], data["input"], info.context.user)
        return cls.success_response(result)

class CustomerCartLinesUpdateQuantity(ModelMutation):
    
    class Arguments:
        id = graphene.ID(description="ID of a cart to update.", required=True)
        input = CustomerCartLinesUpdateQuantityInput(required=False, description="Fields required to update cart.")
    class Meta: 
        description = "Update cart lines quantity."
        model = models.CustomerCart
        object_type = CustomerCartLines
        return_field_name = "cart"
        error_type_class = ScgpCustomerError
        error_type_field = "cart_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cartId = data['id']
        cartInput = data['input']
        lines = cartInput['lines']
        result = update_customer_cart_line_quantity(cartId,lines)
        return cls.success_response(result)
    

