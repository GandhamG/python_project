import graphene

from saleor.graphql.core.mutations import ModelMutation
from saleor.graphql.core.types import NonNullList
from sap_migration.models import Cart, CartLines
from scgp_export.graphql.scgp_export_error import ScgpExportError
from scgp_export.graphql.types import (
    ExportCart,
    ExportCartItem,
)
from scgp_export.graphql.validators import validate_positive_decimal
from scgp_export.implementations.carts import (
    create_export_cart,
    update_draft_export_cart_items,
    update_export_cart
)
from django.db import transaction
from django.db.models import Count
from django.core.exceptions import (
    ValidationError,
    ImproperlyConfigured
)


class ExportCartItemInput(graphene.InputObjectType):
    pi_product_id = graphene.ID(required=True, description="ID of the pi product.")
    quantity = graphene.Float(required=True)


class ExportCartUpdateInput(graphene.InputObjectType):
    lines = NonNullList(
        ExportCartItemInput,
        description=(
            "A list of export cart items, each containing information about "
            "an item in the cart."
        ),
        required=True,
    )


class ExportCartUpdate(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of a export cart to update.", required=True)
        input = ExportCartUpdateInput(required=True, description="Fields required to update cart.")

    class Meta:
        description = "Update cart."
        model = Cart
        object_type = ExportCart
        return_field_name = "cart"
        error_type_class = ScgpExportError
        error_type_field = "cart_errors"

    @classmethod
    def validate_quantity(cls, data):
        lines = data["input"]["lines"]
        for line in lines:
            if float(line["quantity"]) < 0:
                raise ValueError("Quantity must be greater than 0.")

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cls.validate_quantity(data)
        result = update_export_cart(data["id"], data["input"], info.context.user)
        return cls.success_response(result)


class ExportCartCreateInput(graphene.InputObjectType):
    pi_id = graphene.ID(required=True, description="ID of the export pi.")
    sold_to_id = graphene.ID(required=True, description="ID of the sold to.")
    lines = NonNullList(
        ExportCartItemInput,
        description=(
            "A list of export cart items, each containing information about "
            "an item in the cart."
        ),
        required=True,
    )


class ExportCartCreate(ModelMutation):
    class Arguments:
        input = ExportCartCreateInput(
            required=True, description="Fields required to create export cart."
        )

    class Meta:
        description = "Create cart."
        model = Cart
        object_type = ExportCart
        return_field_name = "cart"
        error_type_class = ScgpExportError
        error_type_field = "cart_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        for line in data["input"]["lines"]:
            validate_positive_decimal(line.get("quantity"))
        result = create_export_cart(data["input"], info.context.user)
        return cls.success_response(result)


class ExportCartItemsDelete(ModelMutation):
    status = graphene.String()

    class Meta:
        description = "Delete customer cart items."
        model = CartLines
        object_type = ExportCartItem
        return_field_name = "cart"
        error_type_class = ScgpExportError
        error_type_field = "export_cart_errors"

    class Arguments:
        cart_item_ids = graphene.List(
            graphene.ID, description="ID of cart times to delete", required=True
        )

    @classmethod
    @transaction.atomic
    def _cart_items_delete(cls, items):
        try:
            cart_items = CartLines.objects.filter(
                pk__in=items.get("cart_item_ids")
            )
            cart_id = cart_items[0].cart_id
            cart_items.delete()
            cart_instance = Cart.objects.filter(id=cart_id).annotate(
                num_cart_items=Count("cartlines")
            ).filter(num_cart_items=0).first()
            if cart_instance:
                cart_instance.is_active = False
                cart_instance.save()
            return cart_id
        except Exception as e:
            transaction.set_rollback(True)
            raise ImproperlyConfigured(e)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        lines = CartLines.objects.filter(
            id__in=data["cart_item_ids"], cart__created_by=info.context.user
        )
        if not lines or len(lines) != len(data["cart_item_ids"]):
            raise ValidationError("Cart items do not exist or belong to another user")
        cls._cart_items_delete(data)
        return cls(status=True)

class ExportCartItemDraftInput(graphene.InputObjectType):
    id = graphene.ID(required=True, description="ID of the export cart.")
    quantity = graphene.Float(required=True)

class ExportCartDraftUpdateInput(graphene.InputObjectType):
    lines = NonNullList(
        ExportCartItemDraftInput,
        description=("list of export cart items, each containing information about an item in the cart."),
        required=True
    )

class ExportCartDraftUpdate(ModelMutation):
    class Arguments:
        cart_id = graphene.ID(description="ID of a export cart to update.", required=True)
        input = ExportCartDraftUpdateInput(required=True, description="Fields required to update cart.")

    class Meta:
        description = "Update draft cart."
        model = Cart
        object_type = ExportCart
        return_field_name = "cart"
        error_type_class = ScgpExportError
        error_type_field = "cart_errors" 
    
    @classmethod
    def validate_quantity(cls, data):
        lines = data["input"]["lines"]
        for line in lines:
            if float(line["quantity"]) < 0:
                raise ValueError("Quantity must be greater than 0.")

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cls.validate_quantity(data)
        result = update_draft_export_cart_items(data["input"], data["cart_id"], info.context.user)
        return cls.success_response(result)