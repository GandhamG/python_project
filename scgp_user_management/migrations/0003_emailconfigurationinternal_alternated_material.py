# Generated by Django 3.2.13 on 2023-10-20 17:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_user_management", "0002_scgpuser_sap_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailconfigurationinternal",
            name="alternated_material",
            field=models.BooleanField(default=False),
        ),
    ]
