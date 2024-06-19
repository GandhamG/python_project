from scg_checkout.models import ScgSoldTo
from sap_migration import models as migration_models


def resolve_scg_sold_to(pk):
    return migration_models.SoldToMaster.objects.filter(pk=pk).first()


def resolve_scg_sold_tos():
    return migration_models.SoldToMaster.objects.all()
