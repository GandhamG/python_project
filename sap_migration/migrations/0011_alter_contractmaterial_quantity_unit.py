# Generated by Django 3.2.13 on 2022-09-21 09:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0010_auto_20220921_0831"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contractmaterial",
            name="quantity_unit",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
