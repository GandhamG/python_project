# Generated by Django 3.2.13 on 2022-07-28 10:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_export", "0003_auto_20220728_0727"),
    ]

    operations = [
        migrations.AddField(
            model_name="exportorderline",
            name="net_price",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
