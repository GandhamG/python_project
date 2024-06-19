import graphene

from scg_cognito import error_codes as contract_error_codes

CognitoErrorCode = graphene.Enum.from_enum(contract_error_codes.CognitoErrorCode)
