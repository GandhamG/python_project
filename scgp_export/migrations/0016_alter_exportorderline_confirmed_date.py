# Generated by Django 3.2.13 on 2022-08-22 03:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_export", "0015_merge_20220822_0350"),
    ]

    operations = [
        migrations.AlterField(
            model_name="exportorderline",
            name="confirmed_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
