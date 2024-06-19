import graphene
from django.contrib.auth import get_user_model
from django.contrib.auth import models as auth_models
from graphene import relay

from saleor.graphql.account.types import User
from saleor.graphql.core.types import ModelObjectType
from saleor.graphql.meta.types import ObjectWithMetadata
from scg_customer.graphql.resolves import resolve_sale_groups


class AuthGroup(ModelObjectType):
    name = graphene.String(description="Name of group")

    class Meta:
        description = "Represents user address data."
        interfaces = [relay.Node]
        model = auth_models.Group


class ScgUser(User):
    id = graphene.ID(required=True)
    customer_no = graphene.String()
    sale_groups = graphene.List(AuthGroup)

    class Meta:
        description = "Represents user data."
        interfaces = [relay.Node, ObjectWithMetadata]
        model = get_user_model()

    @staticmethod
    def resolve_sale_groups(root, info):
        return resolve_sale_groups(root.id)

    @staticmethod
    def resolve_customer_no(root, info):
        customer_no = "{:010d}".format(root.id)
        return customer_no
