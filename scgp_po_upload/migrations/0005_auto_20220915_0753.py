# Generated by Django 3.2.13 on 2022-09-15 07:53

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("scgp_po_upload", "0004_auto_20220914_0252"),
    ]

    operations = [
        migrations.AddField(
            model_name="pouploadfilelog",
            name="file",
            field=models.FileField(blank=True, upload_to="po_upload_files"),
        ),
        migrations.AddField(
            model_name="pouploadfilelog",
            name="uploaded_by",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="po_upload_file_logs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="pouploadfilelog",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="pouploadfilelog",
            name="status",
            field=models.CharField(
                choices=[
                    ("in_progress", "In Progress"),
                    ("success", "Success"),
                    ("being_process", "Being Process"),
                    ("fail", "Fail"),
                ],
                default="being_process",
                max_length=255,
            ),
        ),
    ]
