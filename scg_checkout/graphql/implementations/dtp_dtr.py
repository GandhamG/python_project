from datetime import timedelta, datetime

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
import json
from sap_migration import models as migration_models
from sap_migration.graphql.enums import OrderType
from scgp_require_attention_items.graphql.helper import add_class_mark_into_order_line

PASS_VALUE = "Pass"
NOT_PASS_VALUE = "Not Pass"


def data_api_es38():
    data_es38 = {
        "data":
            [
                {
                    "sales_order": "0411480519",
                    "sales_order_item": "20",
                    "delivery": "0416784001",
                    "actual_gi_date": "22.10.2022",
                    "gi_status": "C",
                },
                {
                    "sales_order": "0411480519",
                    "sales_order_item": "30",
                    "delivery": "0416784001",
                    "actual_gi_date": "01.08.2022",
                    "gi_status": "A",
                },
                {
                    "sales_order": "0411480623",
                    "sales_order_item": "20",
                    "delivery": "0416784001",
                    "actual_gi_date": "02.08.2022",
                    "gi_status": "C",
                },
                {
                    "sales_order": "0411480519",
                    "sales_order_item": "10",
                    "delivery": "0416784001",
                    "actual_gi_date": "22.10.2022",
                    "gi_status": "C",
                },
            ]
    }
    return data_es38


def calculate_dtp_dtr(order_line):
    # SEO-4930: skip DTR/DTP calculation for Export order items
    if order_line.order.type == OrderType.EXPORT.value:
        return "", ""

    gi_date = order_line.actual_gi_date
    gi_status = order_line.gi_status
    confirmed_date = order_line.confirmed_date
    original_request_date = order_line.original_request_date
    remark = order_line.remark

    if not gi_date:
        # Cancel GI date
        if gi_status == "A":
            return " ", " "
        # GI date is not available then no need for DTR/DTP calculation
        return "", ""

    dtp, dtr = NOT_PASS_VALUE, NOT_PASS_VALUE

    # Calculate DTP
    if gi_date == confirmed_date or gi_date == confirmed_date - timedelta(days=1):
        dtp = PASS_VALUE

    # Calculate DTR
    if (
            gi_date == original_request_date
            or gi_date == original_request_date - timedelta(days=1)
    ):
        if not remark and dtp == PASS_VALUE:
            dtr = PASS_VALUE
            return dtp, dtr
        dtr = NOT_PASS_VALUE
        return dtp, dtr
    if remark == "C4" and dtp == PASS_VALUE:
        dtr = PASS_VALUE
        return dtp, dtr
    return dtp, dtr


@transaction.atomic
def handle_order_line():
    try:
        data = data_api_es38()
        lines = data["data"]
        order_lines_update = []
        ids = []

        for line in lines:
            so_no = line["sales_order"]
            item_no = line["sales_order_item"]
            delivery = line["delivery"]
            actual_gi_date = line["actual_gi_date"]
            actual_gi_date = datetime.strptime(actual_gi_date, "%d.%m.%Y").strftime('%Y-%m-%d')
            gi_status = line["gi_status"]
            order_line = migration_models.OrderLines.objects.filter(item_no=item_no, order__so_no=so_no,
                                                                    order__type="domestic").first()
            order_line_id = order_line.id
            dtp, dtr = calculate_dtp_dtr(order_line)
            if dtr == NOT_PASS_VALUE and dtp == NOT_PASS_VALUE:
                add_class_mark_into_order_line(order_line, "C3", "C", 1, 4)
            order_line_update = migration_models.OrderLines(
                id=order_line_id,
                dtp=dtp,
                dtr=dtr,
                delivery=delivery,
                gi_status=gi_status,
                actual_gi_date=actual_gi_date,
            )
            order_lines_update.append(order_line_update)
            ids.append(order_line_id)

        if order_lines_update:
            migration_models.OrderLines.objects.bulk_update(
                order_lines_update,
                ["dtp", "dtr", "delivery", "gi_status", "actual_gi_date"]
            )

        order_lines = []
        for order_line_id in ids:
            order_line = migration_models.OrderLines.objects.filter(id=order_line_id).first()
            order_lines.append(order_line)

        return order_lines
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def response_from_sap(path):
    with open(path) as json_file:
        data = json.load(json_file)
    return data
