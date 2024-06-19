import graphene

from saleor.graphql.core.types import SortInputObjectType


class POUploadFileLogField(graphene.Enum):
    UPDATED_AT = ["updated_at", "pk"]


class POUploadFileLogSorterInput(SortInputObjectType):
    class Meta:
        sort_enum = POUploadFileLogField
        type_name = "poUploadFileLogs"
