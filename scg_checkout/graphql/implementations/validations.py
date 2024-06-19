from django.core.exceptions import ValidationError

from scg_checkout.error_codes import ContractCheckoutErrorCode
from scg_checkout.graphql.enums import ScgOrderStatus


def validate_order_exists(order):
    if not order:
        raise ValidationError(
            "order not found.",
            code=ContractCheckoutErrorCode.NOT_FOUND.value,
        )


def validate_cannot_change_order(order):
    if order.status == ScgOrderStatus.CONFIRMED.value:
        raise ValidationError(
            "cannot change order due to order has been confirmed",
            code=ContractCheckoutErrorCode.INVALID.value,
        )
