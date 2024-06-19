import decimal
from datetime import date

from django.core.exceptions import ValidationError

from sap_migration import models
from scg_checkout.error_codes import ContractCheckoutErrorCode
from scg_checkout.graphql.enums import ScgOrderStatus
from sap_migration import models as migration_models


def to_camel_case(snake_str):
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def validate_object(obj, object_name, fields):
    if not obj:
        raise ValidationError(message=f'{to_camel_case(object_name)} is required!')

    for field in fields:
        if not obj.__dict__.get(field, False):
            raise ValidationError(message=f'{to_camel_case(field)} in {to_camel_case(object_name)} is required!')


def validate_objects(objects, obj_name, fields):
    for obj in objects:
        validate_object(obj, obj_name, fields)


def validate_positive_decimal(value, obj_name=""):
    number = decimal.Decimal(value)
    if number <= 0:
        raise ValidationError(f"{obj_name} Value must be greater than 0. Unsupported value: {value}")

    return value


def validate_request_date(order_id, data):
    if data:
        # TODO: improve this
        # change order query from ID to so_no on FE
        order = migration_models.Order.objects.filter(so_no=order_id).first()
        if len(order_id) < 10:
            order = migration_models.Order.objects.filter(id=order_id).first()
        today = date.today()
        request_date_data = order.request_date
        request_date = data.get("request_date")
        if request_date_data != request_date:
            if order.status == ScgOrderStatus.DRAFT.value or (
                    order.status != ScgOrderStatus.DRAFT.value):
                if request_date and request_date < today:
                    raise ValidationError(
                        {
                            "request_date": ValidationError(
                                "Request date must be further than today",
                                code=ContractCheckoutErrorCode.INVALID.value,
                            )
                        }
                    )


def in_range(val, min, max):
    return val >= min and val <= max


def validate_delivery_tol(lines: list):
    for item in lines:
        delivery_tol_over = item.get("over_delivery_tol", None)
        if (delivery_tol_over is not None and
                not in_range(delivery_tol_over, 0, 100)
        ):
            raise ValidationError(
                {
                    "delivery_tol_over": ValidationError(
                        message=f"Over delivery tolerant must be between 0 to 100",
                        code=ContractCheckoutErrorCode.INVALID.value
                    )
                }
            )

        delivery_tol_under = item.get("under_delivery_tol", None)
        if (delivery_tol_under is not None and
                not in_range(delivery_tol_under, 0, 100)
        ):
            raise ValidationError(
                {
                    "delivery_tol_under": ValidationError(
                        message=f"under delivery tolerant must be between 0 to 100",
                        code=ContractCheckoutErrorCode.INVALID.value
                    )
                }
            )


def validate_value_in_range(val, min_value, max_value):
    return min_value <= val <= max_value


def check_object_field_in_range(obj, field_name: str, min_value=0, max_value=100):
    if not obj.get(field_name):
        return
    if not validate_value_in_range(obj.get(field_name), min_value, max_value):
        raise ValidationError(
            {
                f"delivery_tol_{field_name}": ValidationError(
                    message=f"delivery_tol_{field_name} must be between 0 to 100",
                    code=ContractCheckoutErrorCode.INVALID.value
                )
            }
        )


def validate_delivery_tolerance(order_lines: list):
    for order_line in order_lines:
        delivery_tolerance = order_line.get("delivery_tolerance", {})
        check_object_field_in_range(delivery_tolerance, "over", 0, 100)
        check_object_field_in_range(delivery_tolerance, "under", 0, 100)
