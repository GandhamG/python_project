# Generated by Django 3.2.13 on 2023-05-18 09:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_master_data", "0026_auto_20221220_0646"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="conversion2master",
            index=models.Index(
                fields=["material_code"], name="sap_master__materia_2a2a28_idx"
            ),
        ),
    ]
