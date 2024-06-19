import calendar
import decimal

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from sap_migration.models import ContractMaterial, OrderLines
from scgp_export import models
from sap_master_data import models as master_models
from django.db.models import Q

def validate_positive_decimal(value):
    number = decimal.Decimal(value)
    if number <= 0:
        raise ValidationError(f"Value must be greater than 0. Unsupported value: {value}")

    return value


def required_login(func):
    def wrapper(*args, **kwargs):
        info = args[1]
        if isinstance(info.context.user, AnonymousUser):
            raise ValueError("You need to log in")
        res = func(*args, **kwargs)
        return res

    return wrapper


def validate_date(start_date, end_date):
    count_day = end_date - start_date
    leap_year = calendar.isleap(start_date.year)
    if end_date < start_date:
        raise ValueError("End Date must be greater than Start Date")
    if count_day.days > 365:
        if leap_year and start_date.month <= 2 and count_day.days == 366:
            pass
        else:
            raise ValueError("Period of Start Date - End Date maximum to 1 year")

def validate_qty_over_remaining_change_export_order(value, pi_product_id, orderlines_id):
    number = decimal.Decimal(value)
    pi_product = ContractMaterial.objects.get(id=pi_product_id)
    orderlines = OrderLines.objects.filter(Q(id__in=orderlines_id) & Q(material_code=pi_product.material_code))

    conversion_objects = (
        master_models.Conversion2Master.objects.filter(
            material_code=pi_product.material_code,
            to_unit="ROL",
        )
            .order_by("material_code", "-id")
            .distinct("material_code")
            .in_bulk(field_name="material_code")
    )
    conversion_object = conversion_objects.get(str(pi_product.material_code), None)
    calculation = conversion_object and conversion_object.calculation or 0

    total_qty = sum(orderline.quantity for orderline in orderlines) + float(number)

    if calculation:
        total_qty *= round(calculation/1000, 3)
    if total_qty > pi_product.remaining_quantity:
        raise ValidationError("จำนวนสั่งมากกว่าจำนวนคงเหลือ")
    return True

def validate_qty_over_remaining(value, pi_product_id):
    number = decimal.Decimal(value)
    pi_product = ContractMaterial.objects.get(id=pi_product_id)
    if number > pi_product.remaining_quantity:
        raise ValidationError("Input qty is over remaining qty.")
    return True


def validate_alternated_material_filter(kwargs):
    filters = kwargs.get("filter", {})
    created_date, request_date = filters.get('created_date', {}), filters.get('request_date', {})
    if created_date:
        validate_date(created_date.get("gte"), created_date.get("lte"))
    if request_date:
        validate_date(request_date.get("gte"), request_date.get("lte"))

def validate_list_items_equal(lst: list):
    if len(lst) <= 0:
        return True
    return lst.count(lst[0]) == len(lst)

def validate_list_have_item_in(lst: list, haystack: list):
    for item in lst:
        if item in haystack:
            return True
    
    return False
