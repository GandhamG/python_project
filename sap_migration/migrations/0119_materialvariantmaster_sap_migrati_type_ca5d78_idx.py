# Generated by Django 3.2.13 on 2023-06-23 06:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0118_auto_20230622_1104"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="materialvariantmaster",
            index=models.Index(fields=["type"], name="sap_migrati_type_ca5d78_idx"),
        ),
    ]
