from enum import Enum


class ScgpExportErrorCode(Enum):
    ALREADY_EXISTS = "already_exists"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    REQUIRED = "required"
    UNIQUE = "unique"
    IPLAN_ERROR = "iplan_error"
    PRODUCT_GROUP_ERROR = "not_the_same_product_group"
    DUPLICATE_ORDER = "duplicate_order"
