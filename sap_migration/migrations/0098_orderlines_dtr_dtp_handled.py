# Generated by Django 3.2.13 on 2023-02-08 03:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0097_auto_20230206_0806"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderlines",
            name="dtr_dtp_handled",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
    ]
