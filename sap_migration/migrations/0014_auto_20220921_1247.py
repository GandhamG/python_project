# Generated by Django 3.2.13 on 2022-09-21 12:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_master_data", "0012_materialmaster_scgp_material_group"),
        ("sap_migration", "0013_merge_20220921_1134"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="ship_to_country",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="contract",
            name="ship_to_name",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name="contract",
            name="company",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="sap_master_data.companymaster",
            ),
        ),
    ]
