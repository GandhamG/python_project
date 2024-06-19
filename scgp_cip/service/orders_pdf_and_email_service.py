import base64
import logging
from datetime import datetime

import pytz
from django.template.loader import get_template
from django.utils import timezone

from scg_checkout.graphql.enums import CIP_BU
from scg_checkout.graphql.helper import (
    PAYMENT_TERM_MAPPING,
    compute_to_and_cc_list,
    get_date_time_now_timezone_asia_Preview_order_pdf,
    get_internal_emails_by_config,
)
from scg_checkout.graphql.implementations.iplan import (
    get_external_emails_by_config,
    get_sold_to_no_name,
)
from scgp_cip.dao.order.order_repo import OrderRepo
from scgp_cip.dao.order_line.order_line_repo import OrderLineRepo
from scgp_cip.graphql.order.resolves.orders import resolve_preview_domestic_page_order
from scgp_cip.service.helper.preview_order_helper import (
    convert_date_time_to_timezone_asia,
    populate_bill_to_and_ship_to,
)
from scgp_po_upload.graphql.helpers import html_to_pdf
from scgp_user_management.models import EmailConfigurationFeatureChoices


def download_preview_orders_details_in_pdf(info, so_no):
    try:
        date_now = datetime.now().strftime("%d%m%Y")
        file_name_pdf = f"Orders_{so_no}_{date_now}"
        logging.info(f"calling generate pdf for the order id :{so_no}")
        pdf = generate_pdf_file(info, so_no)
        base64_file = base64.b64encode(pdf)
        return file_name_pdf + ".pdf", base64_file.decode("utf-8")
    except Exception as e:
        raise ValueError(e)


def generate_pdf_file(info, order_id):
    details = resolve_preview_domestic_page_order(info, order_id)
    order_header_data = details.get("preview_header_data")
    item = list(details.get("preview_item_data"))
    reduced_item = filter(lambda i: i["reason_reject"] is None, item)
    footer = details.get("preview_footer_data")
    sale_organization = order_header_data["sale_organization"]
    order_header_data[
        "sale_organization"
    ] = f"{sale_organization.full_name}({sale_organization.code}-{sale_organization.short_name})"
    order_header_data["file_name"] = ""
    order_header_data[
        "print_date_time"
    ] = get_date_time_now_timezone_asia_Preview_order_pdf()
    order_header_data["payment_term"] = (
        order_header_data["payment_term"]
        + " "
        + PAYMENT_TERM_MAPPING.get(order_header_data["payment_term"], "")
    )
    order_header_data["message"] = ""
    date_now = datetime.now().strftime("%d%m%Y")
    so_no = order_header_data["so_no"]
    file_name_pdf = f"Orders_{so_no}_{date_now}"
    populate_bill_to_and_ship_to(
        order_header_data["bill_to"], order_header_data["ship_to"], order_header_data
    )
    template_pdf_data = {
        "order_header": order_header_data,
        "data": reduced_item,
        "footer_details": footer,
        "file_name_pdf": file_name_pdf,
    }

    logging.info(f"template data for pdf preparation is : {template_pdf_data}")
    return html_to_pdf(
        template_pdf_data, "preview_order_header.html", "preview_order_content.html"
    )


def send_mail_customer_create_order_cp(info, order, user, partner_emails=None):
    try:
        details = resolve_preview_domestic_page_order(info, order.id)
        order_header_data = details.get("preview_header_data")
        sales_organization = order_header_data["sale_organization"]
        sold_to_code = order.sold_to.sold_to_code
        [_, *_ship_to_list] = order.ship_to and order.ship_to.split(" - ") or []
        template_data = {
            "sale_org_info": f"{sales_organization.full_name} ({sales_organization.code}-{sales_organization.short_name})",
            "order_number": order.so_no,
            "customer_po_number": order_header_data["po_number"],
            "file_name": "",
            "record_date": convert_date_time_to_timezone_asia(order.saved_sap_at),
            "customer_name": order_header_data["customer_name"],
            "place_of_delivery": (" - ".join(_ship_to_list)).strip(),
            "payment_terms": PAYMENT_TERM_MAPPING.get(
                order_header_data["payment_term"], ""
            ),
            "contract_number": "",
            "remark": order.orderextension.additional_txt_header_note1,
        }
        populate_bill_to_and_ship_to(
            order_header_data["bill_to"], order_header_data["ship_to"], template_data
        )
        template = get_template("order_confirmation_email_index.html")
        content = template.render(template_data)
        cc_list, mail_to = prepare_mail_to_cc_create_order(
            order, partner_emails, sold_to_code, user
        )
        subject = f"{sales_organization.short_name} Order submitted : {sold_to_code} {get_sold_to_no_name(sold_to_code, return_only_name=True)}"
        send_mail_to_customer(
            info, order.so_no, mail_to, cc_list, subject, content, True
        )

    except Exception as e:
        raise ValueError(e)


def prepare_mail_to_cc_create_order(order, partner_emails, sold_to_code, user):
    order_lines_db = OrderLineRepo.find_all_order_line_by_order(order)
    product_group = [order_line.material_group2 for order_line in order_lines_db][0]

    internal_emails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.CREATE_ORDER,
        order.sales_organization.code,
        product_group,
        CIP_BU,
    )
    external_email_to_list, external_cc_to_list = get_external_emails_by_config(
        EmailConfigurationFeatureChoices.CREATE_ORDER,
        sold_to_code,
        product_group,
    )
    if partner_emails is None:
        partner_emails = []
    mail_to = list(set(external_email_to_list + [user.email]))
    cc_list = list(set(partner_emails + internal_emails + external_cc_to_list))
    return cc_list, mail_to


def send_mail_to_customer(info, so_no, to, cc, subject, content, order_screen=False):
    try:
        pdf = generate_pdf_file(info, so_no)
        pdf_generated_date = (
            timezone.now().astimezone(pytz.timezone("Asia/Bangkok")).strftime("%d%m%Y")
        )
        file_name = "file"
        if order_screen:
            file_name = f"OrdersCreated_{so_no}_{pdf_generated_date}"
        else:
            file_name = f"Orders_{so_no}_{pdf_generated_date}"

        manager = info.context.manager = info.context.plugins
        manager.scgp_send_order_confirmation_email(
            "scg.email",
            recipient_list=to,
            subject=subject,
            template="order_confirmation_email.html",
            template_data={"content": content},
            cc_list=cc,
            pdf_file=[pdf],
            file_name_pdf=file_name,
        )
    except Exception as e:
        raise ValueError(e)


def get_mail_to_and_cc_list_change_order(sold_to_codes, sale_orgs, feature, so_no):
    order = OrderRepo.get_order_by_id_or_so_no(so_no)
    order_lines_db = OrderLineRepo.find_all_order_line_by_order(order)
    material_group = [order_line.material_group2 for order_line in order_lines_db][0]
    logging.info(f"product group is : {material_group}")
    product_group = [material_group.lower()] if material_group is not None else []
    list_cc, list_to = compute_to_and_cc_list(
        feature,
        True,
        False,
        product_group,
        sale_orgs,
        sold_to_codes,
        CIP_BU,
    )
    return " , ".join(set(list_to)), " , ".join(set(list_cc))
