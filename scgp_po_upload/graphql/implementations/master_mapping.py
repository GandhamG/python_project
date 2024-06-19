from datetime import datetime

from scgp_po_upload.models import PoUploadCustomerSettings


def create_po_upload_customer_settings(user, sold_to_id):
    if not_exits_record(sold_to_id):
        new_instance = PoUploadCustomerSettings(
            created_at=datetime.now(),
            sold_to_id=sold_to_id,
            updated_by_id=user.id,
            use_customer_master=True,
        )
        new_instance.save()
        return new_instance


def not_exits_record(sold_to_id):
    record = PoUploadCustomerSettings.objects.filter(sold_to_id=sold_to_id).first()
    if record:
        raise ValueError("This sold to already exists")
    else:
        return True


def update_po_upload_customer_settings(user, sold_to_id, use_customer_master):
    instance = PoUploadCustomerSettings.objects.filter(sold_to_id=sold_to_id).first()
    if instance:
        instance.use_customer_master = use_customer_master
        instance.updated_at = datetime.now()
        instance.updated_by_id = user.id
        instance.save()
    else:
        raise ValueError("Dose not exits this record")


def delete_po_upload_customer_settings(sold_to_id):
    instance = PoUploadCustomerSettings.objects.filter(sold_to_id=sold_to_id)
    if instance:
        instance.delete()
    else:
        raise ValueError("Dose not exits this record")
    return True

