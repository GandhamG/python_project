# Generated by Django 3.2.13 on 2022-06-13 10:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0166_update_publication_date_and_available_for_purchase"),
        ("scg_contract", "0003_productvariantmaterial_value"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="product_variants",
            field=models.ManyToManyField(
                related_name="contracts", to="product.ProductVariant"
            ),
        ),
    ]
