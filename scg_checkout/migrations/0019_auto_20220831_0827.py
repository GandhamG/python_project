# Generated by Django 3.2.13 on 2022-08-31 08:27

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("scg_checkout", "0018_auto_20220831_0359"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlternativeMaterial",
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
                ("type", models.TextField(blank=True, null=True)),
                ("dia", models.TextField(blank=True, null=True)),
                ("grade", models.CharField(blank=True, max_length=3, null=True)),
                ("gram", models.CharField(blank=True, max_length=3, null=True)),
                (
                    "priority",
                    models.IntegerField(
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="alternative_material_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "material_os",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alternative_material_os",
                        to="scg_checkout.product",
                    ),
                ),
                (
                    "material_own",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alternative_material_own",
                        to="scg_checkout.product",
                    ),
                ),
                (
                    "sales_organization",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.salesorganization",
                    ),
                ),
                (
                    "sold_to",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.scgsoldto",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="alternative_material_updated_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("id",),
                "unique_together": {
                    ("sales_organization", "sold_to", "material_own", "priority")
                },
            },
        ),
        migrations.DeleteModel(
            name="AlternatedMaterial",
        ),
    ]
