from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from sap_migration import models as migration_models
from sap_migration.graphql.enums import OrderType
from scg_checkout.graphql.implementations.dtp_dtr import NOT_PASS_VALUE
from scgp_require_attention_items.graphql.helper import add_class_mark_into_order_line


def calculate_dtp_dtr(order_line):
    from scg_checkout.graphql.implementations.dtp_dtr import calculate_dtp_dtr

    return calculate_dtp_dtr(order_line)


@transaction.atomic
def dtr_dtp_handle():
    try:
        order_lines_update = []
        order_lines = migration_models.OrderLines.objects.filter(
            dtr_dtp_handled=False,
            order__type__in=[OrderType.DOMESTIC.value, OrderType.CUSTOMER.value],
        ).all()
        for order_line in order_lines:
            if (
                order_line.gi_status
                and order_line.actual_gi_date
                and order_line.delivery
                and order_line.original_request_date
            ):
                dtp, dtr = calculate_dtp_dtr(order_line)

                # update db
                order_line.dtp = dtp
                order_line.dtr = dtr
                order_line.dtr_dtp_handled = True
                order_lines_update.append(order_line)
                if dtp == NOT_PASS_VALUE and dtr == NOT_PASS_VALUE:
                    add_class_mark_into_order_line(order_line, "C3", "C", 1, 4)
        migration_models.OrderLines.objects.bulk_update(
            order_lines_update, ["dtp", "dtr", "dtr_dtp_handled"]
        )
        return order_lines

    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)
