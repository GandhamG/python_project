# Generated by Django 3.2.13 on 2022-07-22 03:03

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("scg_checkout", "0013_alter_temporder_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerCart",
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
            ],
        ),
        migrations.CreateModel(
            name="CustomerContract",
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
                ("code", models.CharField(max_length=50)),
                (
                    "project_name",
                    models.CharField(blank=True, max_length=128, null=True),
                ),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("payment_term", models.CharField(max_length=255)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.company",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CustomerContractProductVariant",
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
                ("total_quantity", models.FloatField()),
                ("remaining_quantity", models.FloatField()),
                ("price_per_unit", models.FloatField()),
                (
                    "quantity_unit",
                    models.CharField(blank=True, max_length=12, null=True),
                ),
                ("currency", models.CharField(blank=True, max_length=3, null=True)),
                ("weight", models.FloatField()),
                ("weight_unit", models.CharField(blank=True, max_length=12, null=True)),
                (
                    "contract",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scgp_customer.customercontract",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CustomerOrder",
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
                ("total_price", models.FloatField(blank=True, null=True)),
                ("total_price_inc_tax", models.FloatField(blank=True, null=True)),
                ("tax_amount", models.FloatField(blank=True, null=True)),
                ("status", models.CharField(default="draft", max_length=255)),
                ("order_date", models.DateField(blank=True, null=True)),
                ("order_no", models.CharField(blank=True, max_length=50, null=True)),
                ("request_delivery_date", models.DateField(blank=True, null=True)),
                ("ship_to", models.CharField(blank=True, max_length=255, null=True)),
                ("bill_to", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "unloading_point",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("remark_for_invoice", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "contract",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="scgp_customer.customercontract",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CustomerProduct",
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
                ("name", models.CharField(max_length=255)),
                ("slug", models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name="SoldTo",
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
                ("code", models.CharField(max_length=50)),
                ("name", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "representatives",
                    models.ManyToManyField(
                        blank=True, related_name="sold_tos", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CustomerProductVariant",
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
                ("name", models.CharField(max_length=255)),
                ("slug", models.CharField(max_length=255)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scgp_customer.customerproduct",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CustomerOrderLine",
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
                ("quantity", models.FloatField(blank=True, null=True)),
                (
                    "quantity_unit",
                    models.CharField(blank=True, max_length=12, null=True),
                ),
                ("weight_per_unit", models.FloatField(blank=True, null=True)),
                ("total_weight", models.FloatField(blank=True, null=True)),
                ("price_per_unit", models.FloatField(blank=True, null=True)),
                ("total_price", models.FloatField(blank=True, null=True)),
                ("request_delivery_date", models.DateField(blank=True, null=True)),
                (
                    "contract_variant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scgp_customer.customercontractproductvariant",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scgp_customer.customerorder",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="customercontractproductvariant",
            name="variant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="scgp_customer.customerproductvariant",
            ),
        ),
        migrations.AddField(
            model_name="customercontract",
            name="sold_to",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="scgp_customer.soldto"
            ),
        ),
        migrations.CreateModel(
            name="CustomerCartItem",
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
                ("quantity", models.IntegerField(default=0)),
                (
                    "cart",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scgp_customer.customercart",
                    ),
                ),
                (
                    "contract_variant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scgp_customer.customercontractproductvariant",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="customercart",
            name="contract",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="scgp_customer.customercontract",
            ),
        ),
        migrations.AddField(
            model_name="customercart",
            name="created_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AlterUniqueTogether(
            name="customercart",
            unique_together={("contract", "created_by")},
        ),
    ]
