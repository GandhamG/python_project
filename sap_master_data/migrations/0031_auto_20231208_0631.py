# Generated by Django 3.2.13 on 2023-12-08 06:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_master_data", "0030_bommaterial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CountryMaster",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("country_code", models.CharField(max_length=10, unique=True)),
                ("country_name", models.CharField(max_length=50, null=True)),
            ],
            options={
                "db_table": "sap_master_data_countrymaster",
            },
        ),
        migrations.CreateModel(
            name="TransportZone",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("country_code", models.CharField(max_length=10, null=True)),
                ("transport_zone_code", models.CharField(max_length=20, null=True)),
                ("transport_zone_name", models.CharField(max_length=100, null=True)),
            ],
            options={
                "db_table": "sap_master_data_transportzone",
            },
        ),
        migrations.AddField(
            model_name="materialmaster",
            name="batch_flag",
            field=models.CharField(blank=True, max_length=1, null=True),
        ),
        migrations.AddField(
            model_name="materialplantmaster",
            name="plant_batch_flag",
            field=models.CharField(blank=True, max_length=1, null=True),
        ),
        migrations.AddField(
            model_name="materialplantmaster",
            name="plant_name2",
            field=models.CharField(blank=True, max_length=1, null=True),
        ),
        migrations.AddField(
            model_name="soldtochannelmaster",
            name="credit_area",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name="soldtochannelmaster",
            name="sales_office",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name="soldtochannelmaster",
            name="sales_office_name",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
