# Generated by Django 3.2.13 on 2022-11-16 08:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sap_migration", "0060_auto_20221114_0429"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="payment_term_key",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
