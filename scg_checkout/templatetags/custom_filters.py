# yourapp/templatetags/custom_filters.py

from django import template

register = template.Library()


@register.filter
def is_delivery_qty(order_line):
    return order_line["delivery_qty"] or order_line["delivery_qty"] == 0
