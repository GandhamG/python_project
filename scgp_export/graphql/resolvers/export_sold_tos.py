from django.db.models import Subquery, Q, F, Value
from django.db.models.functions import Concat

from sap_master_data.models import (
    SoldToExternalMaster,
    SoldToMaster,
    SoldToPartnerAddressMaster,
    SoldToChannelMaster,
    SoldToChannelPartnerMaster,
)
from scgp_export import models
from scg_checkout.graphql.helper import get_sold_to_partner


def resolve_export_sold_to(id):
    return SoldToMaster.objects.filter(pk=id).first()


def resolve_export_sold_tos():
    rs = SoldToMaster.objects.filter(account_group_code__in=["DREP", "Z001"], sold_to_code__in=Subquery(
        SoldToChannelMaster.objects.filter(
            Q(distribution_channel_code="30") & (Q(delete_flag__isnull=True) | Q(delete_flag=''))).distinct(
            "sold_to_code").values(
            "sold_to_code"))).all()
    return rs


def resolve_export_order_sold_tos(user):
    return models.ExportSoldTo.objects.filter(exportpi__exportorder__created_by=user).distinct()


def resolve_sold_to_name(sold_to_code):
    sold_to_name = get_sold_to_partner(sold_to_code)
    list_name = ['name1', 'name2', 'name3', 'name4']
    final_name = []
    for name in list_name:
        name_attr = getattr(sold_to_name, name, '')
        if name_attr:
            final_name.append(name_attr)
    return " ".join(final_name)


def resolve_display_text(sold_to_code):
    sold_to_name = SoldToPartnerAddressMaster.objects.filter(partner_code=sold_to_code).first()
    list_name = ['name1', 'name2', 'name3', 'name4']
    final_name = []
    for name in list_name:
        name_attr = getattr(sold_to_name, name, '')
        if name_attr:
            final_name.append(name_attr)
    return " ".join(final_name)


def resolve_domestic_sold_to_search_filter_display_text(root):
    qs = SoldToPartnerAddressMaster.objects.filter(partner_code=root.sold_to_code).annotate(
        full_name=Concat(F("partner_code"), Value(' - '), F('name1'), Value(' '), F('name2'), Value(' '), F('name3'),
                         Value(' '), F('name4'))
    )
    if qs and getattr(root, 'full_name', ''):
        qs = qs.filter(full_name=root.full_name)
    return qs.values_list('full_name', flat=True).first() if qs else f"{root.sold_to_code} - "
