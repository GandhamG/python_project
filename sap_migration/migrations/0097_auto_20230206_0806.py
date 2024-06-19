# Generated by Django 3.2.13 on 2023-02-06 08:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0096_merge_20230206_0749"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderlineiplan",
            name="re_atp_required",
            field=models.BooleanField(null=True),
        ),
        migrations.AddField(
            model_name="orderlineiplan",
            name="request_type",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="orderlineiplan",
            name="single_source",
            field=models.BooleanField(null=True),
        ),
        migrations.AddField(
            model_name="orderlineiplan",
            name="use_consignment_inventory",
            field=models.BooleanField(null=True),
        ),
        migrations.AddField(
            model_name="orderlineiplan",
            name="use_inventory",
            field=models.BooleanField(null=True),
        ),
        migrations.AddField(
            model_name="orderlineiplan",
            name="use_production",
            field=models.BooleanField(null=True),
        ),
        migrations.AddField(
            model_name="orderlineiplan",
            name="use_projected_inventory",
            field=models.BooleanField(null=True),
        ),
    ]
