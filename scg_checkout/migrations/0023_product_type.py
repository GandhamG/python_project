# Generated by Django 3.2.13 on 2022-09-01 08:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scg_checkout", "0022_auto_20220901_0637"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="type",
            field=models.CharField(
                blank=True, default="domestic", max_length=255, null=True
            ),
        ),
    ]
