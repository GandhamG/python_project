import graphene
from graphene import relay

from saleor.graphql.account.types import Company, Division
from saleor.graphql.channel import ChannelContext
from saleor.graphql.channel.types import ChannelContextType
from saleor.graphql.core.connection import CountableConnection, create_connection_slice
from saleor.graphql.core.fields import ConnectionField
from saleor.graphql.core.types import ModelObjectType, NonNullList
from saleor.graphql.meta.types import ObjectWithMetadata
from saleor.graphql.product.types import ProductVariant as ProductVariantBaseType
from saleor.graphql.product.types import ProductVariantCountableConnection
from saleor.order.models import Order, OrderLine
from saleor.product.models import ProductVariant
from scg_contract import models
from scg_contract.graphql.resolves import (
    resolve_business_units,
    resolve_material_by_id,
    resolve_materials_by_product_variant,
    resolve_order_line_by_order_id,
    resolve_product_name,
    resolve_product_variant,
    resolve_total_stock,
)


class Material(ModelObjectType):
    id = graphene.GlobalID(description="ID of material")
    name = graphene.String()
    unit = graphene.String()
    description = graphene.String()

    class Meta:
        model = models.Material


class ScgProductVariant(ProductVariantBaseType):
    materials = graphene.List(
        Material,
        required=True,
        description="List of materials related to product variant.",
    )

    total_stock = graphene.Int()

    class Meta:
        default_resolver = ChannelContextType.resolver_with_context
        description = (
            "Represents a version of a product such as different size or color."
        )
        interfaces = [relay.Node, ObjectWithMetadata]
        model = ProductVariant

    @staticmethod
    def resolve_materials(root, info):
        return resolve_materials_by_product_variant(root.node.id)

    @staticmethod
    def resolve_total_stock(root, info):
        return resolve_total_stock(root.node.id)


class ScgProductVariantCountableConnection(ProductVariantCountableConnection):
    class Meta:
        node = ScgProductVariant


class Contract(ModelObjectType):
    id = graphene.GlobalID(description="ID of scg_contract")
    business_unit = NonNullList(Division)
    company = graphene.Field(Company)
    project_name = graphene.String()
    start_date = graphene.Date()
    end_date = graphene.Date()
    customer_id = graphene.GlobalID(
        required=True, description="ID of scg_customer to view scg_contract"
    )
    payment_term = graphene.String()
    product_variants = ConnectionField(ScgProductVariantCountableConnection)

    class Meta:
        model = models.Contract

    @staticmethod
    def resolve_business_unit(root, info, *_args):
        return resolve_business_units(root.bu_id)

    @staticmethod
    def resolve_product_variants(root, info, *_args, **kwargs):
        instances = root.product_variants.all()
        slice = create_connection_slice(
            instances, info, kwargs, ProductVariantCountableConnection
        )

        edges_with_context = []
        for edge in slice.edges:
            node = edge.node
            edge.node = ChannelContext(node=node, channel_slug=None)
            edges_with_context.append(edge)
        slice.edges = edges_with_context

        return slice


class ContractCountableConnection(CountableConnection):
    class Meta:
        node = Contract


class MaterialCountableConnection(CountableConnection):
    class Meta:
        node = Material


class ProductVariantType(ModelObjectType):
    name = graphene.String()
    sku = graphene.String()

    class Meta:
        model = ProductVariant


class ProductVariantMaterial(ModelObjectType):
    product_name = graphene.String()
    id = graphene.GlobalID(description="ID of product variant")
    value = graphene.Float()
    material = graphene.Field(Material)
    product_variant = graphene.Field(ProductVariantType)

    class Meta:
        model = models.ProductVariantMaterial

    @staticmethod
    def resolve_product_name(root, info, *_args):
        return resolve_product_name(root.product_variant_id)

    @staticmethod
    def resolve_material(root, info, *_args):
        return resolve_material_by_id(root.material_id)

    @staticmethod
    def resolve_product_variant(root, info, *_args):
        return resolve_product_variant(root.product_variant_id)


class ProductVariantMaterialCountableConnection(CountableConnection):
    class Meta:
        node = ProductVariantMaterial


class OrderLineByCustomer(ModelObjectType):
    product_name = graphene.String()
    product_sku = graphene.String()
    quatity = graphene.Int()

    class Meta:
        model = OrderLine


class OrderByCustomer(ModelObjectType):
    id = graphene.GlobalID(description="ID of order")
    status = graphene.String()
    total_net_amount = graphene.Float()
    total_gross_amount = graphene.Float()
    order_lines = NonNullList(OrderLineByCustomer)

    class Meta:
        model = Order

    @staticmethod
    def resolve_order_lines(root, info, *_args):
        return resolve_order_line_by_order_id(root.id)


class OrderByCustomerCountableConnection(CountableConnection):
    class Meta:
        node = OrderByCustomer
