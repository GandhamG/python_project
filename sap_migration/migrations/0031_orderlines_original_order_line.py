# Generated by Django 3.2.13 on 2022-10-04 02:59

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0030_auto_20220930_1634"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderlines",
            name="original_order_line",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="sap_migration.orderlines",
            ),
        ),
    ]
