from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_eo_upload", "0008_auto_20240130_0449"),
    ]

    operations = [
        migrations.RunSQL(
            """
            UPDATE scgp_eo_upload_eouploadlog
            SET updated_at = created_at
            WHERE updated_at IS NULL
            """
        ),
    ]
