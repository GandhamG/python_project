from sap_migration import models as sap_migration_models
from django.db.models import Q

def resolve_product_variants(product_id, info):
    if (
        info.variable_values.get("list_standard_variants") is not None and
        info.variable_values.get("list_non_standard_variants") is not None
    ):
        return sap_migration_models.MaterialVariantMaster.objects.filter(
            Q(code__in=info.variable_values.get("list_standard_variants"), variant_type="Standard") |
            Q(code__in=info.variable_values.get("list_non_standard_variants"), variant_type="Non-Standard")
        ).order_by("description_th")
    return sap_migration_models.MaterialVariantMaster.objects.filter(material_id=product_id)
