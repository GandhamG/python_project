# Generated by Django 3.2.13 on 2022-08-03 03:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_export", "0007_auto_20220802_1003"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="exportorderline",
            unique_together={("order", "pi_product")},
        ),
    ]
