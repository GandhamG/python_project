# Generated by Django 3.2.13 on 2022-09-06 07:32

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scg_checkout", "0026_auto_20220905_0709"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlternatedMaterial",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "new_product",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="material_os",
                        to="scg_checkout.product",
                    ),
                ),
                (
                    "old_product",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="material_own",
                        to="scg_checkout.product",
                    ),
                ),
                (
                    "order_line",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="alternated_material",
                        to="scg_checkout.temporderline",
                    ),
                ),
            ],
        ),
    ]
