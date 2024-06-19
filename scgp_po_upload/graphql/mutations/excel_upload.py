import graphene

from saleor.core.permissions import AuthorizationFilters
from saleor.graphql.core.mutations import BaseMutation
from saleor.graphql.core.types import Upload
from scgp_po_upload.graphql.enums import UploadType
from scgp_po_upload.implementations.excel_upload import validate_excel_upload_file
from scgp_po_upload.implementations.excel_upload_validation import validate_file_name
from scgp_po_upload.graphql.po_upload_error import ScgpPoUploadError

from django.core.files.uploadedfile import InMemoryUploadedFile

PLUGIN_EMAIL = "scg.email"


class ExcelUploadFileMutation(BaseMutation):
    status = graphene.Boolean(default_value=False)
    id = graphene.String()
    created = graphene.String()
    fileName = graphene.String()
    rows = graphene.String()

    class Arguments:
        file = Upload(
            required=True, description="Represents a file in a multipart request."
        )
        order_type = graphene.String()
        sale_org = graphene.String()
        distribution_channel = graphene.String()
        division = graphene.String()
        upload_type = graphene.Argument(UploadType)

    class Meta:
        description = (
            "Upload Excel file. This mutation must be sent as a `multipart` "
            "request. More detailed specs of the upload format can be found here: "
            "https://github.com/jaydenseric/graphql-multipart-request-spec"
        )
        error_type_class = ScgpPoUploadError
        error_type_field = "upload_errors"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        user = info.context.user
        file = info.context.FILES.get(data["file"])
        order_type = data["order_type"]
        sale_org = data["sale_org"]
        distribution_channel = data["distribution_channel"]
        division = data["division"]
        upload_type = data["upload_type"]
        file = InMemoryUploadedFile(
            file=file,
            field_name=file.field_name,
            name=file.name,
            content_type=file.content_type,
            size=file.size,
            charset=file.charset,
            content_type_extra=file.content_type_extra
        )

        validated_data, file_log_instance = validate_excel_upload_file(user, file, order_type, sale_org,
                                                                       distribution_channel, division, upload_type)
        return ExcelUploadFileMutation(status=True, id=file_log_instance.id, created=file_log_instance.created_at,
                                       fileName=file_log_instance.file_name, rows=validated_data)


class CheckExcelFileNameInvalid(BaseMutation):
    valid = graphene.Boolean(description="Excel file name is invalid or not")

    class Arguments:
        file_name = graphene.String(description="file name", required=True)

    class Meta:
        description = "Check if the given excel file is not uploaded in last 30 days"
        error_type_class = ScgpPoUploadError
        error_type_field = "upload_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        file_name = data["file_name"]
        result = validate_file_name(file_name, 30)
        return cls(valid=result)
