# Generated by Django 3.2.13 on 2022-10-06 10:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0036_alter_orderlines_original_quantity"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderlineiplan",
            name="paper_machine",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
