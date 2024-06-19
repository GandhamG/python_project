from django.db.models import Subquery

from sap_master_data.models import SoldToChannelMaster
from sap_migration.models import DistributionChannelMaster


class DistributionChannelMasterRepo:
    @classmethod
    def get_distribution_channel_by_sale_org_code(cls, sale_org_code, channel_type):
        return DistributionChannelMaster.objects.filter(
            code__in=Subquery(
                SoldToChannelMaster.objects.filter(
                    sales_organization_code=sale_org_code
                )
                .distinct("distribution_channel_code")
                .values("distribution_channel_code")
            ),
            type=channel_type,
        ).order_by("code")

    @classmethod
    def get_distribution_channel_by_code(cls, distribution_channel_code):
        return DistributionChannelMaster.objects.filter(
            code=distribution_channel_code
        ).first()
