# Generated by Django 3.2.12 on 2022-06-27 03:28

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scg_checkout", "0003_alter_tempcheckoutline_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="tempcheckoutline",
            name="selected",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="tempcheckoutline",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="scg_checkout.product",
            ),
        ),
    ]
