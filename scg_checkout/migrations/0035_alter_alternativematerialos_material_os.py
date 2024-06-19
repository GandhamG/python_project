# Generated by Django 3.2.13 on 2022-09-10 18:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scg_checkout", "0034_alter_alternativematerialos_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alternativematerialos",
            name="material_os",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="scg_checkout.product",
            ),
        ),
    ]
