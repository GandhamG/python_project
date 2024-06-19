# Generated by Django 3.2.13 on 2023-05-22 05:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_po_upload", "0009_pouploadfilelog_po_numbers"),
        ("sap_migration", "0116_materialvariantmaster_sap_migrati_variant_c696b4_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="po_upload_file_log",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="scgp_po_upload.pouploadfilelog",
            ),
        ),
    ]
