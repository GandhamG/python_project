# Generated by Django 3.2.13 on 2023-02-22 06:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0106_orderlines_item_status_en_rollback"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderlineiplan",
            name="request_iplan_response",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
