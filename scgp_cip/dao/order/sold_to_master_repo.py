from django.db.models import Subquery

from sap_master_data.models import (
    SoldToChannelMaster,
    SoldToChannelPartnerMaster,
    SoldToMaster,
    SoldToPartnerAddressMaster,
    SoldToTextMaster,
)
from scgp_cip.common.constants import OTC_ACCOUNT_GROUPS


class SoldToMasterRepo:
    @classmethod
    def get_by_sales_info(
        cls, sale_org, distribution_channel, division, account_groups
    ):
        return SoldToMaster.objects.filter(
            account_group_code__in=account_groups,
            sold_to_code__in=Subquery(
                SoldToChannelMaster.objects.filter(
                    sales_organization_code=sale_org,
                    distribution_channel_code=distribution_channel,
                    division_code=division,
                )
                .distinct("sold_to_code")
                .values("sold_to_code")
            ),
        )

    @classmethod
    def get_sold_to_channel_partner(
        self, sold_to_code, partner_role, sale_org, distribution_channel, division
    ):
        return SoldToChannelPartnerMaster.objects.filter(
            sold_to_code=sold_to_code,
            partner_role=partner_role,
            sales_organization_code=sale_org,
            distribution_channel_code=distribution_channel,
            division_code=division,
        ).all()

    @classmethod
    def get_sold_to_partner_address(self, sold_to_code, partner_code):
        return SoldToPartnerAddressMaster.objects.filter(
            sold_to_code=sold_to_code,
            partner_code=partner_code,
        ).first()

    @classmethod
    def get_sold_to_partner_address_by_partner(self, partner_no_list):
        return SoldToPartnerAddressMaster.objects.filter(
            partner_code__in=partner_no_list, email__isnull=False
        ).values_list("email", flat=True)

    @classmethod
    def get_sold_to_data(self, sold_to_code):
        return SoldToMaster.objects.filter(sold_to_code=sold_to_code).first()

    @classmethod
    def get_sold_to_partner_data(self, sold_to_code, partner_code):
        return SoldToPartnerAddressMaster.objects.filter(
            partner_code=partner_code, sold_to_code=sold_to_code
        ).first()

    @classmethod
    def get_sold_to_channel_master(
        self, sold_to_code, sales_org, distribution_channel, division
    ):
        return SoldToChannelMaster.objects.filter(
            sold_to_code=sold_to_code,
            sales_organization_code=sales_org,
            distribution_channel_code=distribution_channel,
            division_code=division,
        )

    @classmethod
    def fetch_ship_tos_excluding_selected_ship_to(
        self,
        account_groups,
        sold_to_code,
        partner_role,
        sale_org,
        distribution_channel,
        division,
    ):

        qs = SoldToPartnerAddressMaster.objects.filter(
            sold_to_code__in=Subquery(
                SoldToMaster.objects.filter(
                    account_group_code__in=account_groups,
                    sold_to_code__in=Subquery(
                        SoldToChannelMaster.objects.filter(
                            sales_organization_code=sale_org,
                            distribution_channel_code=distribution_channel,
                            division_code=division,
                        )
                        .distinct("sold_to_code")
                        .values("sold_to_code")
                    ),
                )
                .distinct("sold_to_code")
                .values("sold_to_code")
            )
        ).exclude(
            # sold_to_code=sold_to_code,
            partner_code__in=Subquery(
                SoldToChannelPartnerMaster.objects.filter(
                    sold_to_code=sold_to_code,
                    partner_role=partner_role,
                    sales_organization_code=sale_org,
                    distribution_channel_code=distribution_channel,
                    division_code=division,
                )
                .distinct("partner_code")
                .values("partner_code")
            ),
        )

        return qs

    @classmethod
    def fetch_text_data_for_sold_to(
        self, sold_to_code, sales_org, distribution_channel, division
    ):
        data = (
            SoldToTextMaster.objects.filter(
                sold_to_code=sold_to_code,
                sales_organization_code=sales_org,
                distribution_channel_code=distribution_channel,
                division_code=division,
            )
            .exclude(text_id__isnull=True, language__isnull=True)
            .values("language", "text_id", "text_line")
        )
        return data

    @classmethod
    def filter_otc_sold_to_from_sold_to_list(
        self, sold_to_list, one_time_account_groups
    ):
        return (
            SoldToMaster.objects.filter(
                sold_to_code__in=sold_to_list,
                account_group_code__in=one_time_account_groups,
            )
            .distinct()
            .values_list("sold_to_code", flat=True)
        )

    @classmethod
    def is_otc_sold_to(self, sold_to):
        return SoldToMaster.objects.filter(
            sold_to_code=sold_to,
            account_group_code__in=OTC_ACCOUNT_GROUPS,
        ).first()
