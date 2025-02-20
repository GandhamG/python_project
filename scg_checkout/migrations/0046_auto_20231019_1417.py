# Generated by Django 3.2.13 on 2023-10-19 14:17

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_master_data", "0029_auto_20230623_0642"),
        ("scg_checkout", "0045_alternatedmaterial_order"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alternatedmaterial",
            name="new_product",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="material_os",
                to="sap_master_data.materialmaster",
            ),
        ),
        migrations.AlterField(
            model_name="alternatedmaterial",
            name="old_product",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="material_own",
                to="sap_master_data.materialmaster",
            ),
        ),
    ]
