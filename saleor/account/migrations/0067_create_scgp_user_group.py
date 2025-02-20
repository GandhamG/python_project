# Generated by Django 3.2.13 on 2022-06-07 08:32

from django.db import migrations

from .. import ScgpPermissionGroup


def create_scgp_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")

    Group.objects.get_or_create(name=ScgpPermissionGroup.ADMIN)
    Group.objects.get_or_create(name=ScgpPermissionGroup.CUSTOMER)


class Migration(migrations.Migration):
    operations = [migrations.RunPython(create_scgp_groups, migrations.RunPython.noop)]

    dependencies = [
        ("account", "0066_auto_20220607_0832"),
    ]
