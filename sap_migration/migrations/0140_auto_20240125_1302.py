# Generated by Django 3.2.13 on 2024-01-25 13:02

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0139_remove_orderlinecp_temporder_no"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="orderlinecp",
            name="orderline_id",
        ),
        migrations.AddField(
            model_name="orderlinecp",
            name="order_line",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="sap_migration.orderlines",
            ),
        ),
    ]
