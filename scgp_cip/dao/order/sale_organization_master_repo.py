from django.db.models import Q

from sap_master_data.models import SalesOrganizationMaster
from scgp_cip.common.constants import CIP


class SalesOrganizationMasterRepo:
    @classmethod
    def get_sale_organization_by_code(cls, sale_org_code):
        return SalesOrganizationMaster.objects.filter(code=sale_org_code).first()

    @classmethod
    def get_sales_org_by_user_order_by_bu(cls, scgp_user_id):
        return SalesOrganizationMaster.objects.filter(
            scgpuser__id=scgp_user_id, business_unit__name=CIP
        ).distinct()

    def get_sale_organization_by_sale_org_name(sale_org_name):
        return (
            SalesOrganizationMaster.objects.filter(
                Q(name__in=sale_org_name) | Q(short_name__in=sale_org_name)
            ).values_list("code", flat=True)
            if sale_org_name
            else None
        )

    @classmethod
    def get_bu_by_sale_org(cls, sale_org):
        return SalesOrganizationMaster.objects.get(code=sale_org).business_unit.code
