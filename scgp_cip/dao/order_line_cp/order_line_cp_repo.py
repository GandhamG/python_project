from sap_migration.models import OrderLineCp


class OrderLineCpRepo:
    @classmethod
    def save_order_line_cp(cls, data):
        if isinstance(data, OrderLineCp):
            order_line_cp = data
        else:
            order_line_cp = OrderLineCp(**data)
        order_line_cp.save()
        return order_line_cp

    @classmethod
    def save_order_line_cp_bulk(cls, order_line_cp_list):
        OrderLineCp.objects.bulk_create(order_line_cp_list)

    @classmethod
    def get_order_lines_cp_by_order_line_ids(cls, order_line_ids):
        return OrderLineCp.objects.filter(order_line_id__in=order_line_ids)

    @classmethod
    def get_order_line_cp_by_order_line_id(cls, order_line_id):
        return OrderLineCp.objects.filter(order_line_id=order_line_id).first()

    @classmethod
    def update_order_line_cp_bulk(cls, order_lines_cp, update_fields):
        return OrderLineCp.objects.bulk_update(order_lines_cp, update_fields)

    @classmethod
    def get_order_lines_cp_by_orderid_and_item_nos(cls, order_id, item_nos):
        return (
            OrderLineCp.objects.filter(order_id=order_id, item_no__in=item_nos)
            .distinct("item_no")
            .in_bulk(field_name="item_no")
        )

    @classmethod
    def get_order_line_cp_by_order_id_and_item_no(cls, order, item_no):
        return OrderLineCp.objects.filter(order=order, item_no__in=item_no).first()
