from sap_migration import models as migration_models
from sap_master_data import models as master_models
from scg_checkout.graphql.enums import DistributionChannelType


def resolve_sales_groups(sale_org_code=None):
    sales_groups = migration_models.SalesGroupMaster.objects.all()
    if sale_org_code:
        return sales_groups.filter(sales_organization__code=sale_org_code)
    return sales_groups


def resolve_sales_offices(sale_org_code=None):
    sales_offices = migration_models.SalesOfficeMaster.objects.all()
    if sale_org_code:
        return sales_offices.filter(sales_organization__code=sale_org_code)
    return sales_offices


def resolve_scg_divisions():
    divisions = master_models.DivisionMaster.objects.all()
    return divisions


def resolve_distribution_channels():
    distribution_channels = master_models.DistributionChannelMaster.objects.all()
    return distribution_channels


def resolve_sales_organizations():
    sales_organizations = master_models.SalesOrganizationMaster.objects.all()
    return sales_organizations


def resolve_distribution_channels_domestic():
    distribution_channels = master_models.DistributionChannelMaster.objects.filter(
        type=DistributionChannelType.DOMESTIC.value)
    return distribution_channels


def resolve_distribution_channels_export():
    distribution_channels = master_models.DistributionChannelMaster.objects.filter(
        type=DistributionChannelType.EXPORT.value)
    return distribution_channels


def resolve_distribution_channel_codes(channel_type):
    distribution_channels = master_models.DistributionChannelMaster.objects.filter(
        type=channel_type).values('code')
    return distribution_channels
