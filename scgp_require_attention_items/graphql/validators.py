from datetime import datetime
from sap_migration import models as sap_migration_models
import pytz

tz = pytz.timezone('Asia/Bangkok')
current_date = datetime.now(tz).date()


def validate_overdue_1(request_date):
    item_request_date = datetime.strptime(request_date, "%Y-%m-%d").date()
    if current_date > item_request_date:
        order_lines = sap_migration_models.OrderLines.objects.filter(request_date=request_date)
        for order_line in order_lines:
            order_line.overdue_1 = True
            order_line.save()


def validate_overdue_2(confirmed_date):
    item_confirmed_date = datetime.strptime(confirmed_date, "%Y-%m-%d").date()
    if current_date > item_confirmed_date:
        order_lines = sap_migration_models.OrderLines.objects.filter(confirmed_date=confirmed_date)
        for order_line in order_lines:
            order_line.overdue_2 = True
            order_line.save()
