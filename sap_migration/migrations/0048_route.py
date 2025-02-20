# Generated by Django 3.2.13 on 2022-10-25 09:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0047_auto_20221019_0958"),
    ]

    operations = [
        migrations.CreateModel(
            name="Route",
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
                ("route_code", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "route_description",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
            ],
        ),
    ]
