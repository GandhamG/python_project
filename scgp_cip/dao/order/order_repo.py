from django.db.models import Q

from sap_migration.models import (
    Order,
    OrderExtension,
    OrderOtcPartner,
    OrderOtcPartnerAddress,
)


class OrderRepo:
    @classmethod
    def save_order(cls, data):
        if isinstance(data, Order):
            order = data
        else:
            order = Order(**data)
        order.save()
        return order

    @classmethod
    def save_order_extension(cls, data):
        if isinstance(data, OrderExtension):
            order = data
        else:
            order = OrderExtension(**data)
        order.save()
        return order

    @classmethod
    def get_order_by_id(cls, order_id):
        return Order.objects.get(pk=order_id)

    @classmethod
    def get_order_extension_by_id(cls, order_id):
        return OrderExtension.objects.filter(pk=order_id).first()

    @classmethod
    def save_order_otc_partner(cls, data):
        if isinstance(data, OrderOtcPartner):
            partner = data
        else:
            partner = OrderOtcPartner(**data)
        partner.save()
        return partner

    @classmethod
    def save_order_otc_partneraddress(cls, data):
        if isinstance(data, OrderOtcPartnerAddress):
            address = data
        else:
            address = OrderOtcPartnerAddress(**data)

        address.save()
        return address

    @classmethod
    def get_order_by_id_or_so_no(cls, order_id):
        return Order.objects.filter(Q(id=order_id) | Q(so_no=order_id)).first()

    @classmethod
    def get_order_so_no(cls, sap_order_number):
        return Order.objects.filter(so_no=sap_order_number).all()

    @classmethod
    def get_order_otc_partner(cls, order):
        return OrderOtcPartner.objects.filter(order=order).all()

    @classmethod
    def get_order_by_so_no(cls, so_no):
        return Order.objects.filter(so_no=so_no).first()

    @classmethod
    def bulk_update_order(cls, instance_to_update_header, mapped_order_edited_fields):
        Order.objects.bulk_update(
            [instance_to_update_header], list(mapped_order_edited_fields.keys())
        )

    @classmethod
    def get_order_for_bulk_update(cls, mapped_order_edited_fields, order):
        return Order(id=order.id, **mapped_order_edited_fields)

    @classmethod
    def get_order_extension_for_bulk_update(cls, mapped_order_edited_fields, order_id):
        return OrderExtension(pk=order_id, **mapped_order_edited_fields)

    @classmethod
    def update_order_extension(cls, instance_to_update, mapped_order_edited_fields):
        OrderExtension.objects.bulk_update(
            [instance_to_update], list(mapped_order_edited_fields.keys())
        )

    @classmethod
    def delete_order_otc_partner(cls, otc_partner):
        return otc_partner.delete()

    @classmethod
    def delete_order_otc_partner_address(cls, address):
        return address.delete()

    @classmethod
    def get_otc_partner_count(cls, order):
        return OrderOtcPartner.objects.filter(order=order).count()
