# Generated by Django 3.2.13 on 2022-09-17 06:54

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sap_master_data", "0006_auto_20220910_1403"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlternateMaterial",
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
                ("type", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alternate_material_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "material_own",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.materialmaster",
                    ),
                ),
                (
                    "sales_organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.salesorganizationmaster",
                    ),
                ),
                (
                    "sold_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.soldtomaster",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alternate_material_updated_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Cart",
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
                    "contract_no",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("is_active", models.BooleanField(blank=True, null=True)),
                ("type", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "sold_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.soldtomaster",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ContractMaterial",
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
                    "material_code",
                    models.CharField(blank=True, max_length=500, null=True),
                ),
                (
                    "contract_no",
                    models.CharField(blank=True, max_length=500, null=True),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Order",
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
                ("doc_type", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "sales_group",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "sales_office",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("request_date", models.DateField()),
                (
                    "incoterms_1",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "incoterms_2",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "payment_term",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("po_no", models.CharField(blank=True, max_length=500, null=True)),
                ("po_date", models.DateField()),
                (
                    "price_group",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("price_date", models.DateField()),
                (
                    "delivery_block",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("type", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "contract_no",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_migration.contractmaterial",
                    ),
                ),
                (
                    "currency",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.currencymaster",
                    ),
                ),
                (
                    "customer_group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.customergroupmaster",
                    ),
                ),
                (
                    "customer_group_1",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.customergroup1master",
                    ),
                ),
                (
                    "customer_group_2",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.customergroup2master",
                    ),
                ),
                (
                    "customer_group_3",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.customergroup3master",
                    ),
                ),
                (
                    "customer_group_4",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.customergroup4master",
                    ),
                ),
                (
                    "distribution_channel",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.distributionchannelmaster",
                    ),
                ),
                (
                    "division",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.divisionmaster",
                    ),
                ),
                (
                    "sales_organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.salesorganizationmaster",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OrderItems",
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
                    "customer_material",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("target_quantity", models.FloatField()),
                ("sales_unit", models.CharField(blank=True, max_length=255, null=True)),
                ("plant", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "shipping_point",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("route", models.CharField(blank=True, max_length=255, null=True)),
                ("po_no", models.CharField(blank=True, max_length=255, null=True)),
                ("po_item_no", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "item_category",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "price_group_1",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "price_group_2",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("purch_nos", models.CharField(blank=True, max_length=255, null=True)),
                ("po_date", models.DateField()),
                ("over_delivery_tol", models.FloatField()),
                ("under_delivery_tol", models.FloatField()),
                (
                    "un_limit_tol",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "payment_term_item",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "reject_reason",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("net_weight", models.FloatField()),
                ("gross_weight", models.FloatField()),
                (
                    "product_hierarchy",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "price_group",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "material_pricing_group",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "sales_district",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "storage_location",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("ref_doc", models.CharField(blank=True, max_length=255, null=True)),
                ("ref_doc_it", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "item_no",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_migration.order",
                    ),
                ),
                (
                    "material_no",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.materialmaster",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CartLines",
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
                ("quantity", models.FloatField()),
                (
                    "cart",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_migration.cart",
                    ),
                ),
                (
                    "contract_material",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_migration.contractmaterial",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AlternateMaterialOs",
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
                ("priority", models.IntegerField()),
                (
                    "alternate_material",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_migration.alternatematerial",
                    ),
                ),
                (
                    "material_os",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sap_master_data.materialmaster",
                    ),
                ),
            ],
        ),
    ]
