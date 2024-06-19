import enum

from django.contrib.auth import models as auth_models
from django.contrib.auth.models import Group
from django.db import models

from saleor.account.models import User
from saleor.core.permissions.enums import ScgpPermissions
from sap_migration.models import (
    BusinessUnits,
    DistributionChannelMaster,
    DivisionMaster,
    SalesGroupMaster,
    SalesOfficeMaster,
    SalesOrganizationMaster,
)


class ScgpUserLanguage(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)


class ParentGroup(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True, unique=True)
    groups = models.ManyToManyField(auth_models.Group, related_name="parent_groups")

    class Meta:
        ordering = ("name",)


class ScgpUser(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="scgp_user"
    )
    user_parent_group = models.ForeignKey(
        ParentGroup, on_delete=models.SET_NULL, blank=True, null=True
    )
    ad_user = models.CharField(max_length=50, blank=True)
    employee_id = models.CharField(max_length=50, blank=True)
    sale_id = models.CharField(max_length=10, blank=True)
    customer_type = models.CharField(max_length=256, blank=True)
    company_email = models.EmailField(max_length=50, blank=True, null=True)
    display_name = models.CharField(max_length=50, blank=True, null=True)
    username = models.CharField(max_length=100, unique=True, blank=True, null=True)

    scgp_bus = models.ManyToManyField(BusinessUnits, blank=True)
    scgp_sales_organizations = models.ManyToManyField(
        SalesOrganizationMaster, blank=True
    )
    scgp_sales_groups = models.ManyToManyField(SalesGroupMaster, blank=True)
    scgp_distribution_channels = models.ManyToManyField(
        DistributionChannelMaster, blank=True
    )
    scgp_divisions = models.ManyToManyField(DivisionMaster, blank=True)
    scgp_sales_offices = models.ManyToManyField(SalesOfficeMaster, blank=True)

    created_by = models.ForeignKey(
        User, null=True, on_delete=models.CASCADE, related_name="created"
    )
    updated_by = models.ForeignKey(
        User, null=True, on_delete=models.CASCADE, related_name="updated"
    )
    updated_at = models.DateTimeField(null=True, blank=True)

    languages = models.ManyToManyField(ScgpUserLanguage, blank=True)
    password_wrong = models.IntegerField(default=0, blank=True)
    time_lock = models.DateTimeField(null=True, blank=True)

    # Handle soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="deleted_users", null=True
    )
    email_at_deleted = models.CharField(max_length=256, null=True, blank=True)
    ad_user_at_deleted = models.CharField(max_length=256, null=True, blank=True)
    username_at_deleted = models.CharField(max_length=256, null=True, blank=True)
    sap_id = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        permissions = [
            (x.value.split(".")[1], x.name.replace("_", " ").title())
            for x in ScgpPermissions
        ]


class ScgpUserTokenResetPassword(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=256)


class ScgUserOldPassword(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    password = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)


class EmailConfigurationFeatureChoices(str, enum.Enum):
    CREATE_ORDER = "create_order"
    PO_UPLOAD = "po_upload"
    PENDING_ORDER = "pending_order"
    ORDER_CONFIRMATION = "order_confirmation"
    EO_UPLOAD = "eo_upload"
    REQUIRE_ATTENTION = "require_attention"
    ALTERNATED_MATERIAL = "alternated_material"
    EXCEL_UPLOAD = "excel_upload"

    @classmethod
    def get_choices(cls):
        return (
            (cls.CREATE_ORDER, "Create Order"),
            (cls.PO_UPLOAD, "PO Upload"),
            (cls.PENDING_ORDER, "Pending Order"),
            (cls.ORDER_CONFIRMATION, "Order Confirmation"),
            (cls.EO_UPLOAD, "EO Upload"),
            (cls.REQUIRE_ATTENTION, "Require Attention"),
            (cls.EXCEL_UPLOAD, "Excel Upload"),
        )


class EmailConfigurationExternal(models.Model):
    sold_to_code = models.CharField(max_length=10)
    sold_to_name = models.CharField(max_length=100, blank=True)
    feature = models.CharField(
        max_length=255, choices=EmailConfigurationFeatureChoices.get_choices()
    )
    product_group = models.CharField(max_length=100, null=False, blank=False)
    mail_to = models.CharField(max_length=512, blank=True)
    cc_to = models.CharField(max_length=512, blank=True)

    def get_list_mail_to(self):
        return self.mail_to.split(",")

    def get_list_cc_to(self):
        return self.cc_to.split(",")

    class Meta:
        unique_together = ("sold_to_code", "feature", "product_group")


class EmailInternalMapping(models.Model):
    bu = models.CharField(max_length=255)
    sale_org = models.CharField(max_length=255)
    team = models.CharField(max_length=255)
    product_group = models.CharField(max_length=100, null=False, blank=False)
    email = models.EmailField(max_length=254)

    class Meta:
        unique_together = ("bu", "sale_org", "team", "product_group")


class EmailConfigurationInternal(models.Model):
    bu = models.CharField(max_length=255)
    team = models.CharField(max_length=255)
    create_order = models.BooleanField(default=False)
    po_upload = models.BooleanField(default=False)
    order_confirmation = models.BooleanField(default=False)
    pending_order = models.BooleanField(default=False)
    eo_upload = models.BooleanField(default=False)
    require_attention = models.BooleanField(default=False)
    alternated_material = models.BooleanField(default=False)
    excel_upload = models.BooleanField(default=False)

    class Meta:
        unique_together = (
            "bu",
            "team",
        )


class MenuFunction(models.Model):
    # Group.add_to_class("code", models.CharField(max_length=255, default=""))
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)


class ScgpGroup(models.Model):
    group = models.OneToOneField(
        Group, on_delete=models.CASCADE, related_name="scgp_group"
    )
    code = models.CharField(max_length=255)


class GroupMenuFunctions(models.Model):
    group = models.ForeignKey(
        Group, related_name="group_menu", on_delete=models.CASCADE
    )
    menu_function = models.ForeignKey(
        MenuFunction, related_name="group_menu", on_delete=models.CASCADE
    )
    group_code = models.CharField(max_length=255)
    menu_code = models.CharField(max_length=255)
    group_index = models.IntegerField(default=0, blank=True)
    menu_index = models.IntegerField(default=0, blank=True)

    class Meta:
        db_table = "scgp_user_management_groups_menufunction"
        unique_together = ("group", "menu_function")
