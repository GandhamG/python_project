import uuid
from datetime import datetime, timedelta

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from saleor.account.models import User
from scgp_user_management.models import ScgpUser

MAP_FIELDS_WITH_ATTRS = {
    "scgp_bu_ids": "scgp_bus",
    "scgp_sales_organization_ids": "scgp_sales_organizations",
    "scgp_sales_group_ids": "scgp_sales_groups",
    "scgp_distribution_channel_ids": "scgp_distribution_channels",
    "scgp_division_ids": "scgp_divisions",
    "scgp_sales_office_ids": "scgp_sales_offices",
}


def create_or_update_user_base(params, parent_group, user=None):
    user_data = {
        "email": params.pop("email"),
        "first_name": params.pop("first_name"),
        "last_name": params.pop("last_name"),
        "is_active": params.pop("is_active", True),
    }
    if not user:
        user = User.objects.create(
            is_staff=True if parent_group != "Customer" else False,
            **user_data,
        )
    else:
        user.__dict__.update(
            id=user.id,
            **user_data,
        )
        user.save()

    group_ids = params.pop("group_ids")
    sold_to_ids = params.pop("sold_to_ids", None)
    user.groups.set(group_ids)
    if sold_to_ids:
        user.master_sold_to.set(sold_to_ids)
    return user


def get_user_m2m_fields_input_by_group(input_data, group_name):
    m2m_fields = {}

    if group_name in ["Sales", "Section", "Customer"]:
        return m2m_fields

    m2m_fields["scgp_bu_ids"] = input_data.pop("scgp_bu_ids")
    m2m_fields["scgp_sales_organization_ids"] = input_data.pop(
        "scgp_sales_organization_ids"
    )
    m2m_fields["scgp_sales_group_ids"] = input_data.pop("scgp_sales_group_ids")
    m2m_fields["scgp_distribution_channel_ids"] = input_data.pop(
        "scgp_distribution_channel_ids"
    )
    m2m_fields["scgp_division_ids"] = input_data.pop("scgp_division_ids")
    m2m_fields["scgp_sales_office_ids"] = input_data.pop("scgp_sales_office_ids")
    return m2m_fields


def handler_user_m2m_fields(scgp_user, m2m_fields):
    if not m2m_fields:
        return scgp_user
    for key, value in m2m_fields.items():
        getattr(scgp_user, MAP_FIELDS_WITH_ATTRS[key]).set(value)
    return scgp_user


@transaction.atomic
def scgp_user_create(input_data, current_user, user_parent_group):
    try:
        user_group_name = user_parent_group.name

        # Create Base user
        user_model = create_or_update_user_base(
            params=input_data,
            parent_group=user_group_name,
        )

        # Addition fields for user
        m2m_fields = get_user_m2m_fields_input_by_group(input_data, user_group_name)
        new_user = ScgpUser.objects.create(
            user=user_model,
            created_by=current_user,
            **input_data,
        )
        handler_user_m2m_fields(new_user, m2m_fields)

        return user_model
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


@transaction.atomic
def scgp_user_update(user, input_data, current_user, user_parent_group):
    try:
        user_group_name = user_parent_group.name
        user_updated = create_or_update_user_base(
            params=input_data, parent_group=user_group_name, user=user
        )

        # Addition fields for user
        m2m_fields = get_user_m2m_fields_input_by_group(input_data, user_group_name)

        extend_data = ScgpUser.objects.filter(user=user_updated)
        if not extend_data:
            ScgpUser.objects.create(
                user=user_updated,
                created_by=current_user,
                updated_by=current_user,
                updated_at=timezone.now(),
                **input_data,
            )
        else:
            extend_data.update(
                updated_by=current_user,
                updated_at=timezone.now(),
                **input_data,
            )

        user_extended = ScgpUser.objects.filter(user=user_updated).first()
        handler_user_m2m_fields(user_extended, m2m_fields)

        return user_updated
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def get_object_model_user(email):
    user = User.objects.filter(Q(email=email) | Q(scgp_user__username=email)).first()
    scgp_user = ScgpUser.objects.filter(user=user).first()
    return user, scgp_user


def check_user_lock(email, time_lock_user):
    _, scgp_user = get_object_model_user(email)
    if scgp_user:
        if (
            scgp_user.time_lock
            and scgp_user.time_lock + timedelta(minutes=int(time_lock_user))
            > timezone.now()
        ):
            scgp_user.password_wrong = 0
            scgp_user.save()
            return True
        else:
            scgp_user.time_lock = None
            scgp_user.save()
    return False


def check_wrong_user_password(email, password, wrong_password_number):
    user, scgp_user = get_object_model_user(email)
    if user and scgp_user:
        if not scgp_user.time_lock and not user.check_password(password):
            scgp_user.password_wrong += 1
            if scgp_user.password_wrong == int(wrong_password_number):
                scgp_user.time_lock = datetime.now()
        else:
            scgp_user.password_wrong = 0
        scgp_user.save()
        return True
    return False


@transaction.atomic
def scgp_delete_user(user, current_user):
    try:
        extend_data, _ = ScgpUser.objects.get_or_create(
            user=user,
            defaults={
                "created_by": current_user,
                "updated_by": current_user,
                "updated_at": timezone.now(),
            },
        )
        extend_data.is_deleted = True
        extend_data.deleted_at = timezone.now()
        extend_data.deleted_by = current_user
        extend_data.email_at_deleted = user.email
        extend_data.ad_user_at_deleted = extend_data.ad_user
        extend_data.username_at_deleted = extend_data.username
        extend_data.ad_user = str(uuid.uuid1().int) if extend_data.ad_user else ""
        extend_data.username = str(uuid.uuid1().int) if extend_data.username else None
        extend_data.save()

        user.email = f"{str(uuid.uuid1().int)}@deleted.scgp"
        user.save()

        return "success"
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)
