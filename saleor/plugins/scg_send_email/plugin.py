import logging
import os
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from functools import lru_cache
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend
from django.db.models import Q
from django.template import Context, Template
from django.template.loader import render_to_string

from saleor.account.models import User
from scgp_user_management.models import ScgpUserTokenResetPassword

from ...core.utils.url import prepare_url
from ..base_plugin import BasePlugin, ConfigurationTypeField
from ..email_common import EmailConfig
from . import PLUGIN_ID
from .dataclasses import ScgSendEmailConfig


class ScgEmailPlugin(BasePlugin):
    PLUGIN_ID = PLUGIN_ID
    DEFAULT_CONFIGURATION = [
        {"name": "host", "value": None},
        {"name": "port", "value": None},
        {"name": "username", "value": None},
        {"name": "password", "value": None},
        {"name": "use_ssl", "value": False},
        {"name": "use_tls", "value": False},
        {"name": "sender_name", "value": None},
        {"name": "sender_address", "value": None},
        {"name": "reset_password_url", "value": None},
        {"name": "reset_password_time_out", "value": 60 * 60 * 24 * 7},
        {"name": "reset_password_limit", "value": 10},
        {"name": "password_wrong_number", "value": 10},
        {"name": "time_lock_user", "value": 30},
    ]
    PLUGIN_NAME = "Scg Email"
    CONFIGURATION_PER_CHANNEL = False

    CONFIG_STRUCTURE = {
        "host": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Email host."),
            "label": "Host",
        },
        "port": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Email Port."),
            "label": "Port",
        },
        "username": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Email username."),
            "label": "Username",
        },
        "password": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Email password."),
            "label": "Password",
        },
        "use_ssl": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": ("Email Use SSL."),
            "label": "USE SSL",
        },
        "use_tls": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": ("Email Use TLS."),
            "label": "USE TLS",
        },
        "sender_name": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Email Sender Name."),
            "label": "Send name",
        },
        "sender_address": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Email Sender address."),
            "label": "Send address",
        },
        "reset_password_url": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Reset Password URL."),
            "label": "Reset password url",
        },
        "reset_password_time_out": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Reset Password Time Out."),
            "label": "Reset password time out",
        },
        "reset_password_limit": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Reset Password Limit."),
            "label": "Reset Password Limit",
        },
        "password_wrong_number": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Wrong Password Number"),
            "label": "Wrong Password Number",
        },
        "time_lock_user": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Time Lock User"),
            "label": "Time Lock User",
        },
        "require_attention_url": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Require Attention"),
            "label": "Require Attention",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = ScgSendEmailConfig(
            host=configuration["host"],
            port=configuration["port"],
            username=configuration["username"],
            password=configuration["password"],
            use_ssl=configuration["use_ssl"],
            use_tls=configuration["use_tls"],
            sender_name=configuration["sender_name"],
            sender_address=configuration["sender_address"],
            reset_password_url=configuration["reset_password_url"],
            reset_password_time_out=configuration["reset_password_time_out"],
            reset_password_limit=configuration["reset_password_limit"],
            password_wrong_number=configuration["password_wrong_number"],
            time_lock_user=configuration["time_lock_user"],
            require_attention_url=configuration["require_attention_url"],
        )

        self.email_config = EmailConfig(
            **{
                "host": self.config.host,
                "port": self.config.port,
                "username": self.config.username,
                "password": self.config.password,
                "use_ssl": self.config.use_ssl,
                "use_tls": self.config.use_tls,
                "sender_name": self.config.sender_name,
                "sender_address": self.config.sender_address,
            }
        )

    @lru_cache()
    def logo_data(self, image_name, logo_name):
        try:
            with open(
                os.path.abspath(os.getcwd())
                + f"/scgp_user_management/static/{image_name}",
                "rb",
            ) as f:
                logo_data = f.read()
        except Exception as e:
            logging.info(e)
            with open(
                os.path.abspath(os.getcwd())
                + f"/scgp-eordering-api/scgp_user_management/static/{image_name}",
                "rb",
            ) as f:
                logo_data = f.read()
        logo = MIMEImage(logo_data)
        logo.add_header("Content-ID", f"<{logo_name}>")
        return logo

    def __scgp_send_email(
        self,
        recipient_list: list,
        subject: str,
        template: str,
        template_data: dict,
        pdf_file,
        flag: bool,
        cc_list=None,
        button_reset=False,
        file_name_pdf=None,
    ) -> None:
        logging.info(f"recipient_list: {recipient_list}")
        logging.info(f"cc_list: {cc_list}")
        if isinstance(template, Template):
            html_content = template.render(Context(template_data)).strip()
        else:
            html_content = render_to_string(template, context=template_data).strip()
        message = EmailMultiAlternatives(
            subject=subject,
            body=html_content,
            from_email=self.config.sender_address,
            to=recipient_list,
            connection=EmailBackend(
                host=self.email_config.host,
                port=self.email_config.port,
                username=self.email_config.username,
                password=self.email_config.password,
                use_ssl=self.email_config.use_ssl,
                use_tls=self.email_config.use_tls,
                timeout=5,
            ),
            cc=cc_list,
        )
        message.mixed_subtype = "related"
        message.attach_alternative(html_content, "text/html")
        message.attach(self.logo_data("logo.png", "logo"))
        if button_reset:
            message.attach(self.logo_data("button-reset.png", "button_reset"))

        if flag:
            if file_name_pdf is None:
                file_name_pdf = datetime.now().strftime("%Y/%m/%d")
            if pdf_file:
                if isinstance(pdf_file, list):
                    for pdf in pdf_file:
                        message.attach(f"{file_name_pdf}.pdf", pdf, "application/pdf")
                else:
                    message.attach(f"{file_name_pdf}.pdf", pdf_file, "application/pdf")

        try:
            message.send()
        except Exception as e:
            logging.error("Error send_email: %s", str(e))
            raise e

    def scgp_user_send_reset_mail(
        self, email, token, subject, template, previous_value
    ):
        params = urlencode({"email": email, "token": token})
        reset_url = prepare_url(params, self.config.reset_password_url)
        template_data = {
            "reset_url": reset_url,
            "title": "Forgot your password?",
            "message": """Click on the button below to reset your password. If you did not request a
                    password reset or received this email by mistake, you can safely ignore it. Your password won't be
                    changed.""",
            "button": "Reset Password",
        }

        return self.__scgp_send_email(
            recipient_list=[email],
            subject=subject,
            template=template,
            template_data=template_data,
            pdf_file=None,
            flag=False,
            button_reset=True,
        )

    def scgp_user_send_welcome_mail(
        self, email, token, subject, template, previous_value
    ):
        params = urlencode(
            {
                "email": email,
                "token": token,
            }
        )
        reset_url = prepare_url(params, self.config.reset_password_url)
        template_data = {
            "reset_url": reset_url,
            "title": "Your account has been created successfully",
            "message": """Your account has been created successfully on SCGP E-Ordering. Please click on ‘Reset
            Password’ Button to verify your account and reset your new password.""",
            "button": "Reset Password",
        }

        return self.__scgp_send_email(
            recipient_list=[email],
            subject=subject,
            template=template,
            template_data=template_data,
            pdf_file=None,
            flag=False,
            button_reset=True,
        )

    def scgp_po_upload_send_mail(
        self,
        email,
        template_data,
        subject,
        template,
        pdf_file,
        file_name_pdf,
        previous_value,
        cc_list=None,
    ):
        note = template_data.get("note")
        if note:
            template_data["note"] = note.splitlines()
        else:
            template_data["note"] = None
        return self.__scgp_send_email(
            recipient_list=email if isinstance(email, list) else [email],
            subject=subject,
            template=template,
            template_data=template_data,
            pdf_file=pdf_file,
            flag=True,
            file_name_pdf=file_name_pdf,
            cc_list=cc_list,
        )

    def send_mail_via_attention_type(
        self, email, template_data, subject, template, pdf_file, cc_list, previous_value
    ):

        return self.__scgp_send_email(
            recipient_list=email,
            subject=subject,
            template=template,
            template_data=template_data,
            pdf_file=pdf_file,
            flag=False,
            cc_list=cc_list,
        )

    def scgp_po_upload_send_mail_when_call_api_fail(
        self, recipient_list, template_data, subject, template, cc_list, previous_value
    ):
        return self.__scgp_send_email(
            recipient_list=recipient_list,
            subject=subject,
            template=template,
            template_data=template_data,
            pdf_file=None,
            flag=False,
            cc_list=cc_list,
        )

    def scgp_send_order_confirmation_email(
        self,
        recipient_list,
        template_data,
        subject,
        template,
        cc_list,
        pdf_file,
        previous_value,
        file_name_pdf=None,
    ):
        return self.__scgp_send_email(
            recipient_list=recipient_list,
            subject=subject,
            template=template,
            template_data=template_data,
            pdf_file=pdf_file,
            flag=True,
            cc_list=cc_list,
            file_name_pdf=file_name_pdf,
        )

    def scgp_user_check_valid_token_reset_password(self, email, token, previous_value):
        user = User.objects.filter(
            Q(email=email) | Q(scgp_user__username=email)
        ).first()
        exist_token_reset_password = ScgpUserTokenResetPassword.objects.filter(
            user=user, token=token
        ).first()
        if not exist_token_reset_password:
            return False
        settings.PASSWORD_RESET_TIMEOUT = int(self.config.reset_password_time_out)
        valid_token = default_token_generator.check_token(user, token)
        if not valid_token:
            return False
        return True

    def scgp_user_limit_time_out_reset_password(self, previous_value):
        return self.config.reset_password_limit

    def scgp_user_wrong_password_number(self, previous_value):
        return self.config.password_wrong_number

    def scgp_user_time_lock_user(self, previous_value):
        return self.config.time_lock_user

    def get_require_attention_url(self, previous_value):
        return self.config.require_attention_url

    def scgp_send_email_with_excel_attachment(
        self,
        recipient_list,
        template_data,
        subject,
        template,
        cc_list,
        excel_file,
        previous_value,
        file_name_excel=None,
    ):
        return self.__scgp_send_excel_email(
            recipient_list=recipient_list,
            subject=subject,
            template=template,
            template_data=template_data,
            excel_file=excel_file,
            flag=True,
            cc_list=cc_list,
            file_name_excel=file_name_excel,
        )

    def __scgp_send_excel_email(
        self,
        recipient_list: list,
        subject: str,
        template: str,
        template_data: dict,
        excel_file,
        flag: bool,
        cc_list=None,
        button_reset=False,
        file_name_excel=None,
    ) -> None:
        logging.info(f"recipient_list: {recipient_list}")
        logging.info(f"cc_list: {cc_list}")
        if isinstance(template, Template):
            html_content = template.render(Context(template_data)).strip()
        else:
            html_content = render_to_string(template, context=template_data).strip()
        message = EmailMultiAlternatives(
            subject=subject,
            body=html_content,
            from_email=self.config.sender_address,
            to=recipient_list,
            connection=EmailBackend(
                host=self.email_config.host,
                port=self.email_config.port,
                username=self.email_config.username,
                password=self.email_config.password,
                use_ssl=self.email_config.use_ssl,
                use_tls=self.email_config.use_tls,
                timeout=5,
            ),
            cc=cc_list,
        )
        message.mixed_subtype = "related"
        message.attach_alternative(html_content, "text/html")
        message.attach(self.logo_data("logo.png", "logo"))
        if button_reset:
            message.attach(self.logo_data("button-reset.png", "button_reset"))
        excel_attachment = MIMEBase(
            "application", "vnd.openxmlformats-officedocument.spreadsheetml"
        )
        excel_attachment.set_payload(excel_file)
        encoders.encode_base64(excel_attachment)
        excel_attachment.add_header(
            "Content-Disposition", f'attachment; filename="{file_name_excel}.xlsx"'
        )
        message.attach(excel_attachment)
        try:
            message.send()
        except Exception as e:
            logging.error("Error send_email: %s", str(e))
