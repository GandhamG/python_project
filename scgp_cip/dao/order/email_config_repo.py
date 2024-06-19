from scgp_user_management.models import (
    EmailConfigurationExternal,
    EmailConfigurationInternal,
)


class EmailConfigurationInternalRepo:
    @classmethod
    def get_by_pending_order_and_bu(cls, bu, pending_order):
        return EmailConfigurationInternal.objects.filter(
            pending_order=pending_order, bu=bu
        )

    @classmethod
    def get_by_order_confirmation_and_bu(cls, bu, order_confirmation):
        return EmailConfigurationInternal.objects.filter(
            order_confirmation=order_confirmation, bu=bu
        )


class EmailConfigurationExternalRepo:
    @classmethod
    def get_by_sold_to_and_feature(cls, feature, sold_to_codes):
        return EmailConfigurationExternal.objects.filter(
            sold_to_code__in=sold_to_codes,
            feature=feature,
        )
