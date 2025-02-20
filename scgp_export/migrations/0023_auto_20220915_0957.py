# Generated by Django 3.2.13 on 2022-09-15 09:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_export", "0022_auto_20220906_1742"),
    ]

    operations = [
        migrations.AlterField(
            model_name="exportorderline",
            name="delivery_tol_under",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="exportorderline",
            name="package_quantity",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="exportorderline",
            name="roll_core_diameter",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="exportorderline",
            name="roll_diameter",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="exportorderline",
            name="roll_per_pallet",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
