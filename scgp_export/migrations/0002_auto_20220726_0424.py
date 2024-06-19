# Generated by Django 3.2.13 on 2022-07-26 04:24

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scg_checkout", "0013_alter_temporder_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("scgp_export", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="exportorder",
            old_name="sale_organization",
            new_name="sales_organization",
        ),
        migrations.RenameField(
            model_name="exportorderline",
            old_name="product",
            new_name="pi_product",
        ),
        migrations.AddField(
            model_name="exportorder",
            name="created_by",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="exportorder",
            name="sales_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="scg_checkout.salesgroup",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="exportorder",
            unique_together={("pi", "created_by")},
        ),
    ]
