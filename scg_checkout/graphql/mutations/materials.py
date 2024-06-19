import graphene

from saleor.core.permissions import AuthorizationFilters
from saleor.graphql.core.mutations import BaseMutation
from saleor.graphql.core.types import Upload
from scg_checkout.graphql.contract_checkout_error import ContractCheckoutError
from scg_checkout.graphql.implementations.materials import import_alternative_material


class UploadAlternativeMaterials(BaseMutation):
    status = graphene.Boolean()

    class Arguments:
        file = Upload(
            required=True, description="Represents a file in a multipart request."
        )

    class Meta:
        description = (
            "Upload a file. This mutation must be sent as a `multipart` "
            "request. More detailed specs of the upload format can be found here: "
            "https://github.com/jaydenseric/graphql-multipart-request-spec"
        )
        error_type_class = ContractCheckoutError
        error_type_field = "upload_errors"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        file_data = info.context.FILES.get(data["file"])
        user = info.context.user
        status = import_alternative_material(file_data, user)

        return UploadAlternativeMaterials(status=status)
