from django.db.models import IntegerField, Max, Q
from django.db.models.functions import Cast

from sap_migration.models import OrderLines
from scg_checkout.graphql.enums import ScgOrderStatus


class OrderLineRepo:
    @classmethod
    def save_order_line(cls, data):
        if isinstance(data, OrderLines):
            order_line = data
        else:
            order_line = OrderLines(**data)
        order_line.save()
        return order_line

    @classmethod
    def update_order_line(cls, order_line, fields):
        return order_line.save(update_fields=fields)

    @classmethod
    def find_all_order_line_by_order(cls, order_db):
        return OrderLines.all_objects.filter(order=order_db).order_by("pk").all()

    @classmethod
    def find_order_lines_by_order(cls, order):

        return (
            OrderLines.objects.annotate(
                item_no_int=Cast("item_no", output_field=IntegerField())
            )
            .filter(
                order=order,
                order__status__in=[
                    ScgOrderStatus.DRAFT.value,
                    ScgOrderStatus.PRE_DRAFT.value,
                ],
            )
            .order_by("item_no_int")
        )

    @classmethod
    def save_order_lines(cls, order_lines):
        OrderLines.objects.bulk_create(order_lines)

    @classmethod
    def update_order_lines(cls, existing_order_lines, order_lines_to_update, fields):
        existing_order_lines.bulk_update(order_lines_to_update, fields)

    @classmethod
    def get_order_lines(cls, ids):
        return OrderLines.all_objects.filter(pk__in=ids)

    @classmethod
    def get_order_line(cls, line_id, draft=False):
        if draft:
            return OrderLines.objects.get(pk=line_id)
        else:
            return OrderLines.all_objects.get(pk=line_id)

    @classmethod
    def get_order_lines_by_order_id_without_split(cls, order_id):
        return (
            OrderLines.objects.filter(order_id=order_id, original_order_line_id=None)
            .annotate(
                int_item_no=Cast("item_no", output_field=IntegerField()),
            )
            .order_by("int_item_no", "pk")
        )

    @classmethod
    def get_order_lines_by_order_order_by_item_no(cls, order_db):
        return (
            OrderLines.objects.filter(order=order_db)
            .annotate(
                int_item_no=Cast("item_no", output_field=IntegerField()),
            )
            .order_by("int_item_no", "pk")
        )

    @classmethod
    def delete_order_lines(cls, order_lines):
        deleted_count, _ = order_lines.delete()
        return deleted_count

    @classmethod
    def delete_bom_order_lines_by_parent_id(cls, parent_ids):
        deleted_count, _ = OrderLines.objects.filter(parent_id__in=parent_ids).delete()
        return deleted_count

    @classmethod
    def get_order_line_by_order_id_and_mat_code(cls, order_id, material_code):
        return OrderLines.objects.filter(order_id=order_id, material_code=material_code)

    @classmethod
    def save_order_line_bulk(cls, order_lines):
        return OrderLines.all_objects.bulk_create(order_lines)

    @classmethod
    def update_order_line_bulk(cls, order_lines, update_fields):
        return OrderLines.all_objects.bulk_update(order_lines, update_fields)

    @classmethod
    def get_bom_order_lines_by_parent_id(cls, parent_id):
        return OrderLines.objects.filter(parent_id=parent_id)

    @classmethod
    def get_order_line_gt_item_no(cls, order_id, item_no):
        return (
            OrderLines.objects.annotate(
                int_item_no=Cast("item_no", output_field=IntegerField())
            )
            .filter(order__id=order_id, int_item_no__gt=item_no)
            .order_by("int_item_no", "pk")
        )

    @classmethod
    def get_latest_item_no(cls, order_id):
        return (
            OrderLines.all_objects.filter(order_id=order_id)
            .annotate(numeric_value=Cast("item_no", IntegerField()))
            .aggregate(largest_value=Max("numeric_value"))["largest_value"]
        ) or 0

    @classmethod
    def get_order_line_by_order_distinct_item_no(cls, order):
        return (
            OrderLines.all_objects.filter(order=order)
            .distinct("item_no")
            .in_bulk(field_name="item_no")
        )

    @classmethod
    def get_order_line_dict_by_so_no(cls, so_no):
        return (
            OrderLines.objects.filter(order__so_no=so_no)
            .distinct("item_no")
            .in_bulk(field_name="item_no")
        )

    @classmethod
    def bulk_update(cls, order_line_updates, update_list):
        return OrderLines.all_objects.bulk_update(order_line_updates, update_list)

    @classmethod
    def get_order_line_by_order_no_and_item_no(cls, so_no, item_nos):
        return OrderLines.objects.filter(
            order__so_no=so_no, item_no__in=item_nos
        ).distinct("item_no")

    @classmethod
    def delete_order_lines_by_ids(cls, delete_ids):
        deleted_count, _ = OrderLines.objects.filter(id__in=delete_ids).delete()
        return deleted_count

    @classmethod
    def get_all_related_order_lines(cls, order_line_id, draft=False):
        if draft:
            return (
                OrderLines.all_objects.filter(
                    Q(id=order_line_id) | Q(parent_id=order_line_id)
                )
                .distinct("item_no")
                .order_by("item_no")
            )
        return (
            OrderLines.objects.filter(Q(id=order_line_id) | Q(parent_id=order_line_id))
            .distinct("item_no")
            .order_by("item_no")
        )

    @classmethod
    def delete_all_order_lines_excluding_ids(cls, order, list_line_ids):
        OrderLines.all_objects.filter(order=order).exclude(
            Q(id__in=list_line_ids, draft=False) | Q(item_no__isnull=True)
        ).delete()

    @classmethod
    def get_order_line_by_so_no_and_item_no(cls, so_no, item_no):
        return OrderLines.objects.filter(
            order__so_no=so_no, item_no__in=item_no
        ).first()

    @classmethod
    def get_order_line_by_orders(cls, order_ids):
        return OrderLines.all_objects.filter(order_id__in=order_ids)

    @classmethod
    def update_order_lines_cip(cls, instance_to_update, mapped_order_edited_fields):
        OrderLines.all_objects.bulk_update(
            [instance_to_update], list(mapped_order_edited_fields.keys())
        )

    @classmethod
    def get_order_line_for_bulk_update(cls, mapped_order_edited_fields, item_id):
        return OrderLines(id=item_id, **mapped_order_edited_fields)

    @classmethod
    def get_order_line_by_order_and_item_no(cls, order, item_no):
        return OrderLines.objects.filter(order=order, item_no=item_no).first()

    @classmethod
    def get_order_line_by_order_and_parent_item_no(cls, so_no, parent_item_no):
        return OrderLines.objects.filter(
            order__so_no=so_no, parent__item_no=parent_item_no
        ).first()

    @classmethod
    def update_order_lines_parent_bom(cls, order, parent_line, child_item_nos):
        return OrderLines.objects.filter(
            order=order, item_no__in=child_item_nos
        ).update(parent=parent_line)
