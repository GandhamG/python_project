# Generated by Django 3.2.13 on 2023-12-14 14:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_master_data", "0031_auto_20231208_0631"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bommaterial",
            name="created_date",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AlterField(
            model_name="bommaterial",
            name="last_updated_date",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
