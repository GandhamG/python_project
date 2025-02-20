# Generated by Django 3.2.13 on 2022-06-27 11:39

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("scg_checkout", "0005_alter_tempcheckoutline_product"),
    ]

    operations = [
        migrations.CreateModel(
            name="DistributionChannel",
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
                ("code", models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name="Division",
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
                ("code", models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name="SalesGroup",
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
                ("code", models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name="SalesOffice",
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
                ("code", models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name="SalesOrganization",
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
                ("code", models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name="TempOrder",
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
                ("po_date", models.DateField()),
                ("po_number", models.TextField()),
                ("ship_to", models.TextField()),
                ("bill_to", models.TextField()),
                ("order_type", models.TextField()),
                ("request_date", models.DateField()),
                (
                    "internal_comments_to_warehouse",
                    models.CharField(blank=True, max_length=250, null=True),
                ),
                (
                    "internal_comments_to_logistic",
                    models.CharField(blank=True, max_length=250, null=True),
                ),
                (
                    "external_comments_to_customer",
                    models.CharField(blank=True, max_length=250, null=True),
                ),
                (
                    "product_information",
                    models.CharField(blank=True, max_length=250, null=True),
                ),
                ("total_price", models.FloatField(blank=True, null=True)),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "distribution_channel",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.distributionchannel",
                    ),
                ),
                (
                    "division",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.division",
                    ),
                ),
                (
                    "sale_group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.salesgroup",
                    ),
                ),
                (
                    "sale_office",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.salesoffice",
                    ),
                ),
                (
                    "sale_organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.salesorganization",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="contractproduct",
            name="delivery_over",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contractproduct",
            name="delivery_under",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contractproduct",
            name="plant",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="productvariant",
            name="weight",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tempcheckoutline",
            name="contract_product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="scg_checkout.contractproduct",
            ),
        ),
        migrations.CreateModel(
            name="TempOrderLine",
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
                ("plant", models.CharField(max_length=255)),
                ("quantity", models.FloatField()),
                ("net_price", models.FloatField()),
                ("request_date", models.DateField()),
                (
                    "internal_comments_to_warehouse",
                    models.CharField(blank=True, max_length=250, null=True),
                ),
                ("ship_to", models.TextField(blank=True, null=True)),
                (
                    "product_information",
                    models.CharField(blank=True, max_length=250, null=True),
                ),
                (
                    "contract_product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.contractproduct",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.temporder",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.product",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="scg_checkout.productvariant",
                    ),
                ),
            ],
        ),
    ]
