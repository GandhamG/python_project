# Generated by Django 3.2.13 on 2022-09-21 03:38

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scg_checkout", "0041_alter_temporder_options"),
        ("sap_master_data", "0011_auto_20220920_1105"),
    ]

    operations = [
        migrations.AddField(
            model_name="materialmaster",
            name="scgp_material_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="scg_checkout.scgpmaterialgroup",
            ),
        ),
    ]
