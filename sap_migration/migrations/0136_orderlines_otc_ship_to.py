# Generated by Django 3.2.13 on 2024-01-04 10:04

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0135_merge_20240103_0918"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderlines",
            name="otc_ship_to",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="orderline_shipto",
                to="sap_migration.orderotcpartner",
            ),
        ),
    ]
