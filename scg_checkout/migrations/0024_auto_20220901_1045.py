# Generated by Django 3.2.13 on 2022-09-01 10:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scg_checkout", "0023_product_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="grade",
            field=models.CharField(blank=True, max_length=3, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="gram",
            field=models.CharField(blank=True, max_length=3, null=True),
        ),
    ]
