# Generated by Django 3.2.13 on 2023-05-16 11:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="mulesoftlog",
            name="request_time_ms",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
