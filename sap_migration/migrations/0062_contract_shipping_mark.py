# Generated by Django 3.2.13 on 2022-11-16 11:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0061_auto_20221116_0803"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="shipping_mark",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
