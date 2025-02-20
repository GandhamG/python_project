# Generated by Django 3.2.13 on 2022-11-02 14:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_eo_upload", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="eouploadlog",
            name="order_id",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="eouploadlog",
            name="order_type",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="eouploadlog",
            name="payload",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="eouploadlog",
            name="state",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
