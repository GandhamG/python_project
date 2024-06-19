import graphene

from saleor.graphql.account.types import Company, Division, Office

from .resolves import (
    resolve_auth_groups,
    resolve_companies,
    resolve_contracted_customer,
    resolve_customer,
    resolve_divisions,
    resolve_offices,
)
from .types import AuthGroup, ScgUser


class CustomerQueries(graphene.ObjectType):
    companies = graphene.List(Company)
    divisions = graphene.List(Division)
    offices = graphene.List(Office)
    sale_groups = graphene.List(AuthGroup)
    customer = graphene.Field(
        ScgUser,
        description="look up customer by ID",
        id=graphene.Argument(graphene.ID, description="ID of customer", required=True),
    )
    contracted_customer = graphene.Field(
        ScgUser,
        description="look up contracted customer by ID",
        id=graphene.Argument(
            graphene.ID, description="ID of contracted customer", required=True
        ),
    )

    @staticmethod
    def resolve_companies(self, info, **kwargs):
        return resolve_companies()

    @staticmethod
    def resolve_offices(self, info, **kwargs):
        return resolve_offices()

    @staticmethod
    def resolve_divisions(self, info, **kwargs):
        return resolve_divisions()

    @staticmethod
    def resolve_sale_groups(selfs, info):
        return resolve_auth_groups(info)

    @staticmethod
    def resolve_customer(self, info, **kwargs):
        id = kwargs.get("id")
        return resolve_customer(info, id)

    @staticmethod
    def resolve_contracted_customer(self, info, **kwargs):
        id = kwargs.get("id")
        return resolve_contracted_customer(info, id)
