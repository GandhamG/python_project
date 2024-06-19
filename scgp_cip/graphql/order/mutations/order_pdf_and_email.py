import graphene
from saleor.core.permissions import AuthorizationFilters
from saleor.graphql.core.mutations import (
    ModelMutation,
    BaseMutation
)
from scgp_cip.service.orders_pdf_and_email_service import download_preview_orders_details_in_pdf, send_mail_to_customer
from scg_checkout.graphql.contract_checkout_error import ContractCheckoutError


class PrintOrderFromPreviewPage(BaseMutation):
    exported_file_base_64 = graphene.String()
    file_name = graphene.String()

    class Arguments:
        so_no = graphene.ID(description="ID of a order to print.", required=True)
        sort_type = graphene.String(description="sort type of a order to print.")
    class Meta:
        description = "Download PDF from preview order page"
        error_type_class = ContractCheckoutError

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        so_no = data["so_no"]
        file_name, base64_string = download_preview_orders_details_in_pdf(info, so_no)
        return cls(exported_file_base_64=base64_string, file_name=file_name)


class SendEmailFromChangeOrder(BaseMutation):
    status = graphene.String()

    class Arguments:
        to = graphene.String(required=True)
        cc = graphene.String(required=True)
        subject = graphene.String(required=True)
        content = graphene.String(required=True)
        so_no = graphene.String(required=True)

    class Meta:
        description = "Send Order Email"
        return_field_name = "Email"
        error_type_class = ContractCheckoutError
        error_type_field = "scgp_export_error"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        try:
            recipient_list = data["to"].split(",")
            cc_list = data["cc"].split(",")
            subject = data["subject"]
            content = data["content"]
            so_no = data["so_no"]

            send_mail_to_customer(info, so_no, recipient_list, cc_list, subject, content, False)
            return cls(
                status=True
            )
        except Exception as e:
            raise ValueError(e)
