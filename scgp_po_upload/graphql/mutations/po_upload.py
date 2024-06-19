import graphene
from django.core.exceptions import ValidationError

from saleor.core.permissions import AuthorizationFilters
from saleor.graphql.core.mutations import BaseMutation
from saleor.graphql.core.types import Upload
from scgp_po_upload.graphql.helpers import html_to_pdf
from scgp_po_upload.implementations.po_upload import validate_po_file, retry_upload_file, convert_text_file_encoding
from scgp_po_upload.graphql.po_upload_error import ScgpPoUploadError
from scgp_user_management.graphql.validators import check_valid_email

from django.core.files.uploadedfile import InMemoryUploadedFile

PLUGIN_EMAIL = "scg.email"


class ScgpPoUploadSendMail(BaseMutation):
    message = graphene.String(description="message send mail reset password")

    class Arguments:
        email = graphene.String(required=True, description="Email of user")

    class Meta:
        description = "Scgp PO Upload Send Mail"
        error_type_class = ScgpPoUploadError
        error_type_field = "scgp_po_upload_send_mail_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        email = data["email"]
        if not check_valid_email(email):
            raise ValidationError(
                {

                    "email": ValidationError("Invalid Email format")
                }
            )

        manager = info.context.plugins
        template_data = {
            "order_number": "0412567277",
            "customer_po_number": "SS65072901",
            "file_name": "PO_File_01_29082022.txt",
            "record_date": "29/07/2022 15:35:18 ถึง 29/07/2022 15:35:26",
            "customer_name": "0000002141 - บจก.โอเรียนท์คอนเทนเนอร์",
            "place_of_delivery": "0000002141 - บจก.โอเรียนท์คอนเทนเนอร",
            "payment_terms": "เงินเชื่อ 30 วัน",
            "shipping": "ส่งให้",
            "contract_number": "0412288302",
            "note": "เข้าปกติค่ะ"
        }
        data = [
            {
                'item_no': 10,
                'material_description': 'Z02XS-110D1440117N CA-105D-159 DIA117N',
                'qty': '1',
                'sales_unit': 'ม้วน',
                'qty_ton': 105.874,
                'request_delivery_date': '16.8.2022',
                'iplan_confirm_date': '17.8.2022'
            },
            {
                'item_no': 10,
                'material_description': 'Z02XS-110D1440117N CA-105D-159 DIA117N',
                'qty': '1',
                'sales_unit': 'ม้วน',
                'qty_ton': 105.874,
                'request_delivery_date': '16.8.2022',
                'iplan_confirm_date': '17.8.2022'
            },
            {
                'item_no': 10,
                'material_description': 'Z02XS-110D1440117N CA-105D-159 DIA117N',
                'qty': '1',
                'sales_unit': 'ม้วน',
                'qty_ton': 105.874,
                'request_delivery_date': '16.8.2022',
                'iplan_confirm_date': '17.8.2022'
            }
        ]
        template_pdf_data = {
            'po_no': 'RB22230816',
            'sale_org_name': 'บริษัทสยามคราฟท์อุตสาหกรรมจำกัด / ไทยเคนเปเปอร์',
            'so_no': '411487915',
            'po_no': 'RB22230816',
            'file_name': 'C0001012116_160822_0.1.txt',
            'date_time': '16.08.2022 / 10.31:37',
            'sold_to_no_name': '1012116 บจก. กลุ่มสยามบรรจุภัณฑ์',
            'sold_to_address': '125 หมู่ 1 ต.วังน้ำเย็น จ.ราชบุรี 70160',
            'ship_to_no_sold_to_name': '1012124 โรงงานราชบุรี',
            'ship_to_address': '125 หมู่ 1 ต.วังน้ำเย็น จ.ราชบุรี 70160',
            'payment_method_name': 'เงินเชื่อ 30 วัน',
            'contract_no_name': '410132554 TCRB STD 10/08/22',
            'remark_order_info': '',
            'errors': 'V1024 เอกสารการขาย 410120098 กำลังประมวลผลอยู่ในขณะนี้ (โดยผู้ใช้ S0750030)',
            'data': data

        }
        pdf = html_to_pdf('pdf.html', template_pdf_data)
        manager.scgp_po_upload_send_mail(
            PLUGIN_EMAIL,
            email,
            template_data,
            "TCP Order submitted : 0000002141 - บจก.โอเรียนท์คอนเทนเนอร์",
            'index.html',
            pdf,
            None
        )

        return cls(
            errors=[],
            message="Send mail successfully"
        )


class PoUploadFileMutation(BaseMutation):
    status = graphene.Boolean(default_value=False)

    class Arguments:
        file = Upload(
            required=True, description="Represents a file in a multipart request."
        )
        sold_to_code = graphene.String()

    class Meta:
        description = (
            "Upload PO file. This mutation must be sent as a `multipart` "
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
        ut8_file = convert_text_file_encoding(file.file, 'utf-8')
        file = InMemoryUploadedFile(
            file=ut8_file,
            field_name=file.field_name,
            name=file.name,
            content_type=file.content_type,
            size=ut8_file.getbuffer().nbytes,
            charset=file.charset,
            content_type_extra=file.content_type_extra
        )
        sold_to_code = data.get("sold_to_code")
        validated_data, file_log_instance = validate_po_file(user, file, sold_to_code=sold_to_code)
        return PoUploadFileMutation(status=True)


class PoUploadRetryUploadFile(BaseMutation):
    status = graphene.Boolean(default_value=False)

    class Arguments:
        id = graphene.ID(required=True, description="Id of PO log file")

    class Meta:
        description = "Retry upload file"
        error_type_class = ScgpPoUploadError
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        status = retry_upload_file(data["id"])
        return PoUploadRetryUploadFile(status=status)
