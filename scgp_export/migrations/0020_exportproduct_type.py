# Generated by Django 3.2.13 on 2022-09-01 08:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_export", "0019_auto_20220901_0638"),
    ]

    operations = [
        migrations.AddField(
            model_name="exportproduct",
            name="type",
            field=models.CharField(
                blank=True, default="export", max_length=255, null=True
            ),
        ),
    ]
