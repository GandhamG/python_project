from sap_master_data.models import SoldToChannelMaster


class SoldToChannelMasterRepository:
    @classmethod
    def get_by_sales_info(cls, sold_to, sales_org, distribution_channel):
        return SoldToChannelMaster.objects.filter(
            sold_to_code=sold_to,
            sales_organization_code=sales_org,
            distribution_channel_code=distribution_channel,
        ).first()
