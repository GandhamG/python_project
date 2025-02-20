# Generated by Django 3.2.13 on 2023-08-30 06:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "scgp_require_attention_items",
            "0007_alter_requireattention_inquiry_method_code",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="JobInformation",
            fields=[
                ("unique_id", models.AutoField(primary_key=True, serialize=False)),
                ("status", models.CharField(blank=True, max_length=255, null=True)),
                ("job_type", models.CharField(blank=True, max_length=255, null=True)),
                ("time", models.DateField(blank=True, null=True)),
                ("is_locked", models.BooleanField(default=False)),
            ],
        ),
    ]
