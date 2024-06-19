# Generated by Django 3.2.13 on 2022-08-04 07:59

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_customer", "0006_alter_customerorderline_cart_item"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customercartitem",
            name="cart",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to="scgp_customer.customercart",
            ),
        ),
    ]
