# Generated by Django 3.2.13 on 2023-01-10 08:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0086_merge_20230110_0317"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderlines",
            name="call_atp_ctp",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
    ]
