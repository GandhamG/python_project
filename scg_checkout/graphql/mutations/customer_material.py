import logging
import time
import graphene

from saleor.core.permissions import AuthorizationFilters
from saleor.graphql.core.mutations import BaseMutation
from saleor.graphql.core.types import Upload
from scg_checkout.graphql.contract_checkout_error import ContractCheckoutError
from scg_checkout.graphql.customer_material_upload_error import CustomerMaterialUploadError
from scg_checkout.graphql.implementations.customer_materials import import_customer_material_mappings, \
    export_customer_material_template_file
from scg_checkout.graphql.implementations.orders import download_customer_material_excel
from scg_checkout.graphql.types import CustomerMaterialUploadInput


class UploadCustomerMaterials(BaseMutation):
    status = graphene.Boolean()
    rows = graphene.String()

    class Arguments:
        file = Upload(
            required=True, description="Represents a file in a multipart request."
        )
        input = CustomerMaterialUploadInput(
            required=True,
            description="User Input Fields required to Upload the file")

    class Meta:
        description = (
            "Upload a file. This mutation must be sent as a `multipart` "
            "request. More detailed specs of the upload format can be found here: "
            "https://github.com/jaydenseric/graphql-multipart-request-spec"
        )
        error_type_class = CustomerMaterialUploadError
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        file_data = info.context.FILES.get(data["file"])
        input_param = data["input"]
        user = info.context.user

        status, rows = import_customer_material_mappings(input_param, file_data, user)
        logging.info(f"[Customer Material Mapping:Upload] "
                     f" Time Taken to complete request: {time.time() - start_time} seconds")

        return UploadCustomerMaterials(status=status, rows=rows)


class CustomerMaterialTemplateExport(BaseMutation):
    file_name = graphene.String()
    content_type = graphene.String()
    exported_file_base_64 = graphene.String()

    class Meta:
        description = "Export Customer Material Mapping template and return link to download"
        error_type_class = ContractCheckoutError

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        file_name, content_type, base64_string = export_customer_material_template_file(info)
        logging.info(f"[Customer Material Mapping:Download Template] "
                     f" Time Taken to complete request: {time.time() - start_time} seconds")
        return CustomerMaterialTemplateExport(
            file_name=file_name,
            content_type=content_type,
            exported_file_base_64=base64_string
        )


class DownloadCustomerMaterialExcel(BaseMutation):
    exported_file_base_64 = graphene.String()
    file_name = graphene.String()
    error_message = graphene.String()
    success = graphene.Boolean()

    class Arguments:
        sold_to_code = graphene.String()
        sale_organization_id = graphene.String()
        distribution_channel_id = graphene.ID()

    class Meta:
        description = "Download Customer Master Mappings based on search"
        return_field_name = "Excel"
        error_type_class = ContractCheckoutError
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        try:
            success, file_name, base64_string, message = download_customer_material_excel(data, info)
            return cls(success=success, exported_file_base_64=base64_string, file_name=file_name, error_message=message)
        except Exception as e:
            raise ValueError(e)
