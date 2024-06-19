# Generated by Django 3.2.13 on 2024-03-07 08:45

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("scgp_user_management", "0006_merge_20240307_0841"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="scgpuser",
            options={
                "permissions": [
                    ("scgp_view_order_customer", "View Order Customer"),
                    ("scgp_create_order_customer", "Create Order Customer"),
                    ("scgp_change_order_customer", "Change Order Customer"),
                    ("scgp_view_order_domestic", "View Order Domestic"),
                    ("scgp_create_order_domestic", "Create Order Domestic"),
                    ("scgp_change_order_domestic", "Change Order Domestic"),
                    ("scgp_view_order_export", "View Order Export"),
                    ("scgp_create_order_export", "Create Order Export"),
                    ("scgp_change_order_export", "Change Order Export"),
                    ("scgp_view_nrc_order_domestic", "View Order Domestic Nrc"),
                    ("scgp_create_nrc_order_domestic", "Create Order Domestic Nrc"),
                    ("scgp_change_nrc_order_domestic", "Change Order Domestic Nrc"),
                    ("scgp_view_dummy", "View Dummy"),
                    ("scgp_create_dummy", "Create Dummy"),
                    ("scgp_change_dummy", "Change Dummy"),
                    ("scgp_approve_dummy", "Approve Dummy"),
                    ("scgp_maintain_user", "Maintain User"),
                    ("scgp_maintain_user_group", "Maintain User Group"),
                    ("scgp_maintain_role", "Maintain Role"),
                    ("scgp_maintain_role_permission", "Maintain Role Permission"),
                    ("scgp_maintain_organization", "Maintain Organization"),
                    ("scgp_maintain_alt_material", "Maintain Alt Material"),
                    ("scgp_maintain_po_upload", "Maintain Po Upload"),
                    ("scgp_maintain_email", "Maintain Email"),
                    ("scgp_maintain_email_eo_upload", "Maintain Email Eo Upload"),
                    ("scgp_maintain_customer_material", "Maintain Customer Material"),
                    ("scgp_all_upload_po_customer", "All Upload Po Customer"),
                    ("scgp_all_upload_po_admin", "All Upload Po Admin"),
                    ("scgp_all_contract", "All Contract"),
                    ("scgp_all_report_customer", "All Report Customer"),
                    ("scgp_all_report_admin", "All Report Admin"),
                    ("scgp_all_report_domestic", "All Report Domestic"),
                    ("scgp_all_report_export", "All Report Export"),
                    ("scgp_view_stock", "View Stock"),
                    ("scgp_view_draft_order", "View Draft Order"),
                    ("scgp_nrc_excel_upload", "Excel Upload"),
                    ("scgp_all_report_nrc_domestic", "All Report Domestic Nrc"),
                ]
            },
        ),
    ]
