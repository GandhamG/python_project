import logging
import time

import graphene

from saleor.graphql.core.mutations import BaseMutation
from scg_checkout.graphql.contract_checkout_error import ContractCheckoutError
from scgp_cip.service.excel_upload_service import export_excel_upload_template_file


class ExcelUploadTemplateExport(BaseMutation):
    file_name = graphene.String()
    content_type = graphene.String()
    exported_file_base_64 = graphene.String()

    class Meta:
        description = "Export Excel Upload template and return link to download"
        error_type_class = ContractCheckoutError

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        start_time = time.time()
        file_name, content_type, base64_string = export_excel_upload_template_file(info)
        logging.info(f"[Excel Upload:Download Template] "
                     f" Time Taken to complete request: {time.time() - start_time} seconds")
        return ExcelUploadTemplateExport(
            file_name=file_name,
            content_type=content_type,
            exported_file_base_64=base64_string
        )