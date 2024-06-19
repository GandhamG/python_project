# Generated by Django 3.2.13 on 2022-09-30 04:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0026_merge_20220929_1010"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="route",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="shipping_point",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
