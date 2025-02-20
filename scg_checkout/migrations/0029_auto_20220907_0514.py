# Generated by Django 3.2.13 on 2022-09-07 05:14

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scg_checkout", "0028_auto_20220906_1911"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="alternativematerial",
            unique_together={("sales_organization", "sold_to", "material_own")},
        ),
        migrations.CreateModel(
            name="AlternativeMaterialOs",
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
                    "priority",
                    models.IntegerField(
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "alternative_material",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.alternativematerial",
                    ),
                ),
                (
                    "material_os",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.product",
                    ),
                ),
            ],
            options={
                "ordering": ("id",),
            },
        ),
        migrations.RemoveField(
            model_name="alternativematerial",
            name="material_os",
        ),
        migrations.RemoveField(
            model_name="alternativematerial",
            name="priority",
        ),
    ]
