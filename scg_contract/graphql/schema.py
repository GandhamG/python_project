import graphene

from saleor.graphql.account.types import User
from saleor.graphql.core.connection import (
    create_connection_slice,
    filter_connection_queryset,
)
from saleor.graphql.core.fields import FilterConnectionField, PermissionsField
from saleor.graphql.core.utils import from_global_id_or_error
from saleor.graphql.product.types.products import Product

from .filters import ContractFilterInput
from .resolves import (
    resolve_customer_contract,
    resolve_customer_contracts,
    resolve_material,
    resolve_materials,
    resolve_materials_by_product,
    resolve_orders_by_customer_id,
)
from .types import Contract, ContractCountableConnection
from .types import Material as MaterialType
from .types import (
    MaterialCountableConnection,
    OrderByCustomerCountableConnection,
    ProductVariantMaterialCountableConnection,
)


class ContractQueries(graphene.ObjectType):
    customer_contracts = FilterConnectionField(
        ContractCountableConnection,
        description="Look up scg_contract by scg_customer ID",
        customer_id=graphene.Argument(
            graphene.Int, description="ID of an scg_customer", required=True
        ),
        filter=ContractFilterInput(),
    )
    customer_contract = graphene.Field(
        Contract,
        description="Look up scg_contract by contract ID",
        id=graphene.Argument(
            graphene.ID, description="ID of an contract", required=True
        ),
    )

    orders_by_customer_id = FilterConnectionField(
        OrderByCustomerCountableConnection,
        customer_id=graphene.Argument(
            graphene.ID, description="ID of an customer", required=True
        ),
        description="Look up order by customer",
    )

    material = PermissionsField(
        MaterialType,
        id=graphene.Argument(graphene.ID, description="ID of material"),
        description="Look up a material by ID",
    )

    materials = FilterConnectionField(
        MaterialCountableConnection,
        description="Look up list material",
    )

    materials_by_product = FilterConnectionField(
        ProductVariantMaterialCountableConnection,
        product_id=graphene.Argument(graphene.ID, description="ID of product"),
        description="Look up material by product ID",
    )

    def resolve_customer_contract(self, info, id):
        _, id = from_global_id_or_error(id, Contract)
        return resolve_customer_contract(info, id)

    def resolve_customer_contracts(self, info, **kwargs):
        customer_id = kwargs.get("customer_id")
        qs = resolve_customer_contracts(info, customer_id)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(qs, info, kwargs, ContractCountableConnection)

    def resolve_material(self, info, **data):
        material_pk = data.get("id")
        _, id = from_global_id_or_error(material_pk, MaterialType)
        return resolve_material(id)

    def resolve_materials(self, info, **kwargs):
        qs = resolve_materials()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(qs, info, kwargs, MaterialCountableConnection)

    def resolve_materials_by_product(self, info, **kwargs):
        product_id = kwargs.get("product_id")
        _, id = from_global_id_or_error(product_id, Product)
        qs = resolve_materials_by_product(id)
        return create_connection_slice(
            qs, info, kwargs, ProductVariantMaterialCountableConnection
        )

    def resolve_orders_by_customer_id(self, info, **kwargs):
        customer_id = kwargs.get("customer_id")
        _, id = from_global_id_or_error(customer_id, User)
        qs = resolve_orders_by_customer_id(id)
        return create_connection_slice(
            qs, info, kwargs, OrderByCustomerCountableConnection
        )
