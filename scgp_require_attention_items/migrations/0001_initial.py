# Generated by Django 3.2.13 on 2022-09-04 20:22

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RequireAttentionItems",
            fields=[
                (
                    "unique_id",
                    models.CharField(max_length=255, primary_key=True, serialize=False),
                ),
                ("order_line_id", models.IntegerField()),
                ("type", models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                "db_table": "scgp_require_attention_items",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="RequireAttentionMaterial",
            fields=[
                (
                    "unique_id",
                    models.CharField(max_length=255, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(blank=True, max_length=255, null=True)),
                ("code", models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                "db_table": "scgp_require_attention_material",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="RequireAttentionSoldTo",
            fields=[
                (
                    "unique_id",
                    models.CharField(max_length=255, primary_key=True, serialize=False),
                ),
                ("code", models.CharField(blank=True, max_length=255, null=True)),
                ("name", models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                "db_table": "scgp_require_attention_sold_to",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="RequireAttentionView",
            fields=[
                (
                    "unique_id",
                    models.CharField(max_length=255, primary_key=True, serialize=False),
                ),
                (
                    "order_line_id",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("type", models.CharField(blank=True, max_length=255, null=True)),
                ("items_id", models.CharField(blank=True, max_length=255, null=True)),
                ("order_no", models.CharField(blank=True, max_length=255, null=True)),
                ("item_no", models.FloatField()),
                ("ship_to", models.CharField(blank=True, max_length=255, null=True)),
                ("sold_to", models.CharField(blank=True, max_length=255, null=True)),
                ("request_date", models.DateField(blank=True, null=True)),
                ("confirmed_date", models.DateField(blank=True, null=True)),
                ("po_no", models.CharField(blank=True, max_length=255, null=True)),
                ("plant", models.CharField(blank=True, max_length=255, null=True)),
                ("status", models.CharField(blank=True, max_length=255, null=True)),
                ("unit", models.CharField(blank=True, max_length=255, null=True)),
                ("material", models.CharField(blank=True, max_length=500, null=True)),
                ("mat_code", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "mat_description",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "request_quantity",
                    models.FloatField(blank=True, max_length=255, null=True),
                ),
                ("grade", models.CharField(blank=True, max_length=255, null=True)),
                ("gram", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "attention_type",
                    models.CharField(
                        blank=True,
                        default="Confirm date diff",
                        max_length=255,
                        null=True,
                    ),
                ),
                ("iplant_confirm_quantity", models.FloatField(blank=True, null=True)),
                (
                    "item_status",
                    models.CharField(
                        blank=True,
                        default="Partial Committed Order",
                        max_length=255,
                        null=True,
                    ),
                ),
                ("original_date", models.DateField(blank=True, null=True)),
                (
                    "overdue_1",
                    models.BooleanField(blank=True, default=False, null=True),
                ),
                (
                    "overdue_2",
                    models.BooleanField(blank=True, default=False, null=True),
                ),
                (
                    "inquiry_method_code",
                    models.CharField(
                        blank=True, default="JIT", max_length=255, null=True
                    ),
                ),
                ("transportation_method", models.IntegerField(blank=True, null=True)),
                (
                    "type_of_delivery",
                    models.CharField(
                        blank=True, default="Arrival", max_length=255, null=True
                    ),
                ),
                (
                    "fix_source_assignment",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "split_order_item",
                    models.CharField(
                        blank=True, default="Yes", max_length=255, null=True
                    ),
                ),
                (
                    "partial_delivery",
                    models.CharField(
                        blank=True, default="Yes", max_length=255, null=True
                    ),
                ),
                (
                    "consignment",
                    models.CharField(
                        blank=True,
                        default="1000 - Free Stock",
                        max_length=255,
                        null=True,
                    ),
                ),
            ],
            options={
                "db_table": "scgp_require_attention_view",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="RequireAttention",
            fields=[
                (
                    "items",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        serialize=False,
                        to="scgp_require_attention_items.requireattentionitems",
                    ),
                ),
                (
                    "attention_type",
                    models.CharField(
                        blank=True,
                        default="Confirm date diff",
                        max_length=255,
                        null=True,
                    ),
                ),
                ("iplant_confirm_quantity", models.FloatField(blank=True, null=True)),
                (
                    "item_status",
                    models.CharField(
                        blank=True,
                        default="Partial Committed Order",
                        max_length=255,
                        null=True,
                    ),
                ),
                ("original_date", models.DateField(blank=True, null=True)),
                (
                    "overdue_1",
                    models.BooleanField(blank=True, default=False, null=True),
                ),
                (
                    "overdue_2",
                    models.BooleanField(blank=True, default=False, null=True),
                ),
                (
                    "inquiry_method_code",
                    models.CharField(
                        blank=True, default="JIT", max_length=255, null=True
                    ),
                ),
                ("transportation_method", models.IntegerField(blank=True, null=True)),
                (
                    "type_of_delivery",
                    models.CharField(
                        blank=True, default="Arrival", max_length=255, null=True
                    ),
                ),
                (
                    "fix_source_assignment",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "split_order_item",
                    models.CharField(
                        blank=True, default="Yes", max_length=255, null=True
                    ),
                ),
                (
                    "partial_delivery",
                    models.CharField(
                        blank=True, default="Yes", max_length=255, null=True
                    ),
                ),
                (
                    "consignment",
                    models.CharField(
                        blank=True,
                        default="1000 - Free Stock",
                        max_length=255,
                        null=True,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RequireAttentionIPlan",
            fields=[
                (
                    "items",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        serialize=False,
                        to="scgp_require_attention_items.requireattentionitems",
                    ),
                ),
                ("atp_ctp", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "atp_ctp_detail",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("block", models.CharField(blank=True, max_length=255, null=True)),
                ("run", models.CharField(blank=True, max_length=255, null=True)),
            ],
        ),
        migrations.RunSQL(
            """
            CREATE TABLE scgp_require_attention_items as
            SELECT
                concat(sctol.id,'-',sctol.type) AS unique_id,
                sctol.id as order_line_id,
                sctol.type
                from scg_checkout_temporderline sctol
            union all
            SELECT
                concat(seeol.id,'-',seeol.type) as unique_id,
                seeol.id as order_line_id,
                seeol.type
                from scgp_export_exportorderline seeol
            """
        ),
        migrations.RunSQL(
            """
            ALTER TABLE scgp_require_attention_items
            ADD CONSTRAINT PK_unique_id PRIMARY KEY (unique_id)
            """
        ),
        migrations.RunSQL(
            """
            CREATE VIEW scgp_require_attention_material as
            SELECT
            concat(scp.id,'-',scp.type) as unique_id,
            scp.name,
            scp.grade,
            scp.gram,
            scp.code,
            scp.material_group_id
            FROM scg_checkout_product scp
            UNION ALL
            SELECT
            concat(see.id,'-',see.type) as unique_id,
            see.name,
            see.grade,
            see.gram,
            see.slug,
            see.material_group_id
            FROM scgp_export_exportproduct see
            """
        ),
        migrations.RunSQL(
            """
            CREATE VIEW scgp_require_attention_sold_to AS
            SELECT
            concat(scst.id,'-',scst.code) as unique_id,
            scst.code,
            scst.name
            FROM scg_checkout_scgsoldto scst
            UNION ALL
            SELECT concat(seest.id,'-',seest.code),
            seest.code,
            seest.name
            FROM scgp_export_exportsoldto seest
            """
        ),
        migrations.RunSQL(
            """
            CREATE VIEW scgp_require_attention_items_view as
                SELECT
                concat(sctol.id,'-',sctol.type) AS unique_id,
                sctol.id as order_line_id,
                sctol.type,
                scto.order_no,
                sctol.item_no,
                scto.ship_to,
                CASE WHEN scto.sold_to_id IS null
                    THEN null
                    ELSE concat(scst.code, ' - ' ,scst.name)
                    END as sold_to ,
                sctol.request_date,
                sctol.confirmed_date,
                scto.po_number as po_no,
                scp.name as material,
                scp.code  as mat_code,
                scpv.name as mat_description,
                scp.material_group_id as material_group_id,
                scp.grade,
                scp.gram,
                sctol.quantity as request_quantity,
                scp.sales_unit as unit,
                sctol.plant,
                scto.status,
                scto.sale_organization_id as sales_organization_id,
                scto.sale_group_id as sales_group_id,
                CASE WHEN scto.scgp_sales_employee_id is null
                     THEN null
                     ELSE concat(scse.code,' - ',scse.name)
                     END as scgp_sales_employee_id
                FROM scg_checkout_temporderline sctol
                INNER JOIN scg_checkout_temporder scto on sctol.order_id = scto.id
                INNER JOIN account_user au on scto.customer_id = au.id
                LEFT  JOIN scg_checkout_scgsoldto scst on scto.sold_to_id = scst.id
                INNER JOIN scg_checkout_product scp on sctol.product_id = scp.id
                INNER JOIN scg_checkout_productvariant scpv on sctol.variant_id = scpv.id
                LEFT JOIN scg_checkout_scgpsalesemployee scse on scto.scgp_sales_employee_id = scse.id
                UNION ALL
                SELECT
                concat(seeol.id,'-',seeol.type) as unique_id,
                seeol.id as order_line_id,
                seeol.type,
                seeo.order_no,
                seeol.item_no,
                seeo.ship_to,
                concat(seest.code,' - ',seest.name) as sold_to,
                seeol.request_date,
                seeol.confirmed_date,
                seeo.po_no as po_no,
                seep.name as material,
                seep.slug  as mat_code,
                seep.description as mat_description,
                seep.material_group_id as material_group_id,
                seep.grade,
                seep.gram,
                seeol.quantity as request_quantity,
                seeol.weight_unit,
                seeol.plant,
                seeo.status,
                seeo.sales_organization_id as sales_organization_id,
                seeo.sales_group_id as sales_group_id,
                CASE WHEN seeo.scgp_sales_employee_id IS null
                    THEN null
                    ELSE concat(scse.code,' - ',scse.name)
                    END as scgp_sales_employee_id
                FROM scgp_export_exportorderline seeol
                INNER JOIN scgp_export_exportorder seeo on seeol.order_id = seeo.id
                INNER JOIN scgp_export_exportpi seepi on seeo.pi_id = seepi.id
                INNER JOIN scgp_export_exportsoldto seest on seest.id = seepi.sold_to_id
                INNER JOIN scgp_export_exportpiproduct seepip  on seeol.pi_product_id = seepip.id
                INNER JOIN scgp_export_exportproduct seep on seepip.product_id = seep.id
                LEFT  JOIN scg_checkout_scgpsalesemployee scse on seeo.scgp_sales_employee_id  = scse.id
            """
        ),
        migrations.RunSQL(
            """
            CREATE VIEW scgp_require_attention_view as
                SELECT * FROM scgp_require_attention_items_view sraiv
                JOIN scgp_require_attention_items_requireattention sra
                ON sraiv.unique_id = sra.items_id
            """
        ),
        migrations.RunSQL(
            """
            create or replace function scg_checkout_temporderline_insert()
            returns trigger as
            $$
            begin
                insert
                into
                scgp_require_attention_items ("unique_id",
                "order_line_id",
                "type")
            values (
            Concat(cast(new."id" as text), '-', new."type"),
            new."id",
            new."type");
            return new;
            end;
            $$
            language 'plpgsql';
            """
        ),
        migrations.RunSQL(
            """
            DROP TRIGGER IF EXISTS scg_checkout_temporderline_insert
            ON "scg_checkout_temporderline";
            CREATE TRIGGER scg_checkout_temporderline_insert
            AFTER INSERT
            ON "scg_checkout_temporderline"
            FOR EACH ROW
            EXECUTE PROCEDURE scg_checkout_temporderline_insert();
            """
        ),
        migrations.RunSQL(
            """
            create or replace
            function scgp_exportorderline_insert()
            returns trigger as
            $$
            begin
                insert
                into
                scgp_require_attention_items ("unique_id",
                "order_line_id",
                "type")
            values (
            Concat(cast(new."id" as text), '-', new."type"),
            new."id",
            new."type");
            return new;
            end;
            $$
            language 'plpgsql';
            """
        ),
        migrations.RunSQL(
            """
            DROP TRIGGER IF EXISTS scgp_exportorderline_insert
            ON "scgp_export_exportorderline";
            CREATE TRIGGER scgp_exportorderline_insert
            AFTER INSERT
            ON "scgp_export_exportorderline"
            FOR EACH ROW
            EXECUTE PROCEDURE scgp_exportorderline_insert();
            """
        ),
        migrations.RunSQL(
            """
            create or replace
            function scg_checkout_temporderline_delete()
            returns trigger as
            $$
            begin
               delete from "scgp_require_attention_items" where "type" = old."type" and "order_line_id" = cast(old."id" as int8);
               return null;
            end;
            $$
            language 'plpgsql';
            """
        ),
        migrations.RunSQL(
            """
            DROP TRIGGER IF EXISTS scg_checkout_temporderline_delete
            ON "scg_checkout_temporderline";
            CREATE TRIGGER scg_checkout_temporderline_delete
            AFTER delete
            ON "scg_checkout_temporderline"
            FOR EACH ROW
            EXECUTE PROCEDURE scg_checkout_temporderline_delete();
            """
        ),
        migrations.RunSQL(
            """
            create or replace
            function scgp_exportorderline_delete()
            returns trigger as
            $$
            begin
               delete from "scgp_require_attention_items" where "type" = old."type" and "order_line_id" = cast(old."id" as int8);
               return null;
            end;
            $$
            language 'plpgsql';
            """
        ),
        migrations.RunSQL(
            """
            DROP TRIGGER IF EXISTS scgp_exportorderline_delete
            ON "scgp_export_exportorderline";
            CREATE TRIGGER scgp_exportorderline_delete
            AFTER delete
            ON "scgp_export_exportorderline"
            FOR EACH ROW
            EXECUTE PROCEDURE scgp_exportorderline_delete();
            """
        ),
    ]
