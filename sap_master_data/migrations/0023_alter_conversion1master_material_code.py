# Generated by Django 3.2.13 on 2022-12-09 09:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_master_data", "0022_alter_materialmaster_material_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="conversion1master",
            name="material_code",
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
    ]
