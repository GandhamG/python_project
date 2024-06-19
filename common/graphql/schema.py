import graphene

from common.graphql.mutations.mulesoft_api import MulesoftAPILogCreate


class MulesoftAPILogMutations(graphene.ObjectType):
    mulesoft_api_log_create = MulesoftAPILogCreate.Field()