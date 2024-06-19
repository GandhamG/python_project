# Generated by Django 3.2.13 on 2022-08-19 07:46

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scg_checkout", "0014_alter_temporderline_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorganization",
            name="business_unit",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="business_units",
                to="scg_checkout.businessunit",
            ),
        ),
    ]
