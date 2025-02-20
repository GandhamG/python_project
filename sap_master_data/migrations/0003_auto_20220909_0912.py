# Generated by Django 3.2.13 on 2022-09-09 02:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_master_data", "0002_soldtomaterialmaster"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="conversion2master",
            name="material_code",
        ),
        migrations.AddField(
            model_name="materialsalemaster",
            name="distribution_channel_status",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="materialsalemaster",
            name="distribution_channel_status_desc",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="materialsalemaster",
            name="distribution_channel_status_valid_from",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="materialsalemaster",
            name="xchannel_status",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="materialsalemaster",
            name="xchannel_status_desc",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="materialsalemaster",
            name="xchannel_status_valid_from",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
