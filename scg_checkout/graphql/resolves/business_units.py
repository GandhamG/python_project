from django.db.models import Count
from sap_migration import models as migration_models


def resolve_business_units():
    business_units = migration_models.BusinessUnits.objects.annotate(num_company=Count('company_master')) \
        .filter(num_company__gt=0)
    return business_units


def resolve_business_unit(info, id):
    business_unit = migration_models.BusinessUnits.objects.filter(id=id).first()
    return business_unit
