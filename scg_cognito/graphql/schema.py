import graphene

from .mutations import GenerateTokenFromCognito


class CognitoMutations(graphene.ObjectType):
    generate_token = GenerateTokenFromCognito.Field()
