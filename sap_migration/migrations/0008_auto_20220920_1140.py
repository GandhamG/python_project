# Generated by Django 3.2.13 on 2022-09-20 11:40

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0007_auto_20220920_1105"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="internal_comment_to_warehouse",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="production_information",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="order",
            name="contract",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="sap_migration.contract",
            ),
        ),
    ]
