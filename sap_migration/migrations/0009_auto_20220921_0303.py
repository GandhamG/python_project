# Generated by Django 3.2.13 on 2022-09-21 03:03

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0008_contract_sold_to"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartlines",
            name="material",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="sap_master_data.materialmaster",
            ),
        ),
        migrations.AddField(
            model_name="cartlines",
            name="material_variant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="sap_migration.materialvariantmaster",
            ),
        ),
        migrations.AddField(
            model_name="contract",
            name="business_unit",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="sap_migration.businessunits",
            ),
        ),
        migrations.AddField(
            model_name="contract",
            name="company",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="sap_master_data.companymaster",
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="scgp_sales_employee",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="sap_migration.salesemployee",
            ),
        ),
    ]
