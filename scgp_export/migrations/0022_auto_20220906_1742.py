# Generated by Django 3.2.13 on 2022-09-06 17:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_export", "0021_auto_20220901_1045"),
    ]

    operations = [
        migrations.AddField(
            model_name="exportorderline",
            name="overdue_1",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
        migrations.AddField(
            model_name="exportorderline",
            name="overdue_2",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
    ]
