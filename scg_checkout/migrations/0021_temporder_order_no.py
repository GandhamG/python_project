# Generated by Django 3.2.13 on 2022-08-31 17:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scg_checkout", "0020_auto_20220831_1634"),
    ]

    operations = [
        migrations.AddField(
            model_name="temporder",
            name="order_no",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
