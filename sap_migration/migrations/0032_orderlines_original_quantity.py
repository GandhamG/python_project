# Generated by Django 3.2.13 on 2022-10-04 04:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0031_orderlines_original_order_line"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderlines",
            name="original_quantity",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
