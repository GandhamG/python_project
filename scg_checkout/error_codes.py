from enum import Enum


class ContractCheckoutErrorCode(str, Enum):
    ALREADY_EXISTS = "already_exists"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    REQUIRED = "required"
    UNIQUE = "unique"
    CONTRACT_ERROR = "not_the_same_contract"
    PRODUCT_GROUP_ERROR = "not_the_same_product_group"
    DUPLICATE_ORDER = "duplicate_order"
