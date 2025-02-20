# Generated by Django 3.2.13 on 2022-10-03 09:18

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0030_auto_20220930_1634"),
        ("scg_checkout", "0042_auto_20220927_0734"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alternatedmaterial",
            name="new_product",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="material_os",
                to="sap_migration.materialvariantmaster",
            ),
        ),
        migrations.AlterField(
            model_name="alternatedmaterial",
            name="old_product",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="material_own",
                to="sap_migration.materialvariantmaster",
            ),
        ),
    ]
