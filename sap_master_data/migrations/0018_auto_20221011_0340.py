# Generated by Django 3.2.13 on 2022-10-11 03:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_master_data", "0017_incoterm1master"),
    ]

    operations = [
        migrations.AddField(
            model_name="textidmaster",
            name="section",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name="textidmaster",
            name="code",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]
