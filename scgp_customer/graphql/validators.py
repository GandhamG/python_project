import decimal

from django.core.exceptions import ValidationError


def validate_positive_decimal(quantity):
    if quantity < 0:
        raise ValidationError(f"Value must be greater than 0. Unsupported value: {quantity}")

    return quantity


def validate_quantity(data):
    lines = data["input"]["lines"]
    for line in lines:
        if float(line["quantity"]) < 0:
            raise ValueError("Quantity must be greater than 0.")
