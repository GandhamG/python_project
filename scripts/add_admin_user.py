from saleor.account.models import User
from scgp_user_management.models import ParentGroup, ScgpUser


def add_admin_user():
    admin, _ = User.objects.get_or_create(
        email="admin@admin.com",
        is_staff=True,
        first_name="Firstname",
        last_name="Lastname",
    )
    admin.set_password("P@ssw0rd")
    admin.save()

    admin_group = ParentGroup.objects.get(code="ADMIN")

    ScgpUser.objects.get_or_create(
        display_name="externaladmin", user=admin, user_parent_group=admin_group
    )

    return
