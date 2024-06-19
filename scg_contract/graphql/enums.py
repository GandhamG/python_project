import graphene

from scg_contract import error_codes as contract_error_codes

ContractErrorCode = graphene.Enum.from_enum(contract_error_codes.ContractErrorCode)
