from django.db.models import Subquery

from sap_master_data.models import SoldToChannelMaster
from sap_migration.models import DivisionMaster


class DivisionMasterRepo:
    @classmethod
    def get_division_by_sale_org_code(cls, sale_org_code):
        return DivisionMaster.objects.filter(
            code__in=Subquery(
                SoldToChannelMaster.objects.filter(
                    sales_organization_code=sale_org_code
                )
                .distinct("division_code")
                .values("division_code")
            )
        ).order_by("code")

    @classmethod
    def get_division_by_code(cls, division_code):
        return DivisionMaster.objects.filter(code=division_code).first()
