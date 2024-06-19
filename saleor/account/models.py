from typing import Union

from django.conf import settings
from django.contrib.auth.models import _user_has_perm  # type: ignore
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    Group,
    Permission,
    PermissionsMixin,
)
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import JSONField  # type: ignore
from django.db.models import Q, QuerySet, Value
from django.db.models.expressions import Exists, OuterRef
from django.forms.models import model_to_dict
from django.utils import timezone
from django.utils.crypto import get_random_string
from django_countries.fields import Country, CountryField
from phonenumber_field.modelfields import PhoneNumber, PhoneNumberField
from versatileimagefield.fields import VersatileImageField

from ..app.models import App
from ..channel.models import Channel
from ..core.models import ModelWithMetadata
from ..core.permissions import AccountPermissions, BasePermissionEnum, get_permissions
from ..core.utils.json_serializer import CustomJsonEncoder
from ..order.models import Order
from . import CustomerEvents
from .validators import validate_possible_number


class PossiblePhoneNumberField(PhoneNumberField):
    """Less strict field for phone numbers written to database."""

    default_validators = [validate_possible_number]


class AddressQueryset(models.QuerySet):
    def annotate_default(self, user):
        # Set default shipping/billing address pk to None
        # if default shipping/billing address doesn't exist
        default_shipping_address_pk, default_billing_address_pk = None, None
        if user.default_shipping_address:
            default_shipping_address_pk = user.default_shipping_address.pk
        if user.default_billing_address:
            default_billing_address_pk = user.default_billing_address.pk

        return user.addresses.annotate(
            user_default_shipping_address_pk=Value(
                default_shipping_address_pk, models.IntegerField()
            ),
            user_default_billing_address_pk=Value(
                default_billing_address_pk, models.IntegerField()
            ),
        )


class Address(models.Model):
    first_name = models.CharField(max_length=256, blank=True)
    last_name = models.CharField(max_length=256, blank=True)
    company_name = models.CharField(max_length=256, blank=True)
    street_address_1 = models.CharField(max_length=256, blank=True)
    street_address_2 = models.CharField(max_length=256, blank=True)
    city = models.CharField(max_length=256, blank=True)
    city_area = models.CharField(max_length=128, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = CountryField()
    country_area = models.CharField(max_length=128, blank=True)
    phone = PossiblePhoneNumberField(blank=True, default="", db_index=True)

    objects = models.Manager.from_queryset(AddressQueryset)()

    class Meta:
        ordering = ("pk",)
        indexes = [
            GinIndex(
                name="address_search_gin",
                # `opclasses` and `fields` should be the same length
                fields=["first_name", "last_name", "city", "country"],
                opclasses=["gin_trgm_ops"] * 4,
            ),
        ]

    @property
    def full_name(self):
        return "%s %s" % (self.first_name, self.last_name)

    def __str__(self):
        if self.company_name:
            return "%s - %s" % (self.company_name, self.full_name)
        return self.full_name

    def __eq__(self, other):
        if not isinstance(other, Address):
            return False
        return self.as_data() == other.as_data()

    __hash__ = models.Model.__hash__

    def as_data(self):
        """Return the address as a dict suitable for passing as kwargs.

        Result does not contain the primary key or an associated user.
        """
        data = model_to_dict(self, exclude=["id", "user"])
        if isinstance(data["country"], Country):
            data["country"] = data["country"].code
        if isinstance(data["phone"], PhoneNumber):
            data["phone"] = data["phone"].as_e164
        return data

    def get_copy(self):
        """Return a new instance of the same address."""
        return Address.objects.create(**self.as_data())


class UserManager(BaseUserManager):
    def create_user(
        self, email, password=None, is_staff=False, is_active=True, **extra_fields
    ):
        """Create a user instance with the given email and password."""
        email = UserManager.normalize_email(email)
        # Google OAuth2 backend send unnecessary username field
        extra_fields.pop("username", None)

        user = self.model(
            email=email, is_active=is_active, is_staff=is_staff, **extra_fields
        )
        if password:
            user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        from django.db import transaction
        from django.db.models import Count

        from sap_master_data.models import (
            DistributionChannelMaster,
            DivisionMaster,
            SalesOrganizationMaster,
        )
        from sap_migration.models import BusinessUnits, SalesGroupMaster
        from scg_checkout.models import SalesOffice
        from scgp_user_management.implementations.scgp_users import (
            handler_user_m2m_fields,
        )
        from scgp_user_management.models import ParentGroup, ScgpUser

        try:
            with transaction.atomic():

                # Create a superuser
                super_user = self.create_user(
                    email, password, is_staff=True, is_superuser=True, **extra_fields
                )

                # Extract user details from email
                ad_user = email.split("@")[0]
                emp_id = "CSAdmin"
                firstname = "Admin"
                lastname = email.split("@")[0]

                # Set user details
                super_user.first_name = firstname
                super_user.last_name = lastname

                # Set user groups based on group names
                group_names = [
                    "Inquiry",
                    "Shopping domestic",
                    "Shopping export",
                    "Maintain",
                    "PO Upload",
                    "Inquiry Domestic",
                    "Inquiry Export",
                ]
                groups = Group.objects.filter(name__in=group_names)
                group_ids = list(groups.values_list("id", flat=True))
                super_user.groups.set(group_ids)

                # Create ScgpUser instance
                try:
                    selected_index = ParentGroup.objects.get(name="Admin").id
                except ParentGroup.DoesNotExist:
                    selected_index = None
                input_data = {
                    "ad_user": ad_user,
                    "employee_id": emp_id,
                    "user_parent_group_id": selected_index,
                }
                user_extended = ScgpUser.objects.create(
                    user=super_user,
                    created_by=super_user,
                    updated_by=super_user,
                    **input_data,
                )

                # Fetch IDs from SalesGroupMaster table
                sales_group_ids_queryset = SalesGroupMaster.objects.values_list(
                    "id", flat=True
                )
                sales_group_ids = [
                    str(group_id) for group_id in sales_group_ids_queryset
                ]

                # Fetch IDs from DistributionChannelMaster table
                distribution_channel_ids_queryset = (
                    DistributionChannelMaster.objects.values_list("id", flat=True)
                )
                distribution_channel_ids = [
                    str(channel_id) for channel_id in distribution_channel_ids_queryset
                ]

                # Fetch IDs from SalesOrganizationMaster table
                sales_organization_ids_queryset = (
                    SalesOrganizationMaster.objects.values_list("id", flat=True)
                )
                sales_organization_ids = [
                    str(channel_id) for channel_id in sales_organization_ids_queryset
                ]

                # Fetch IDs from DivisionMaster table
                divisionaster_ids_queryset = DivisionMaster.objects.values_list(
                    "id", flat=True
                )
                divisionaster_ids = [
                    str(channel_id) for channel_id in divisionaster_ids_queryset
                ]

                # Fetch IDs from SalesOffice table
                salesoffice_ids_queryset = SalesOffice.objects.values_list(
                    "id", flat=True
                )
                salesoffice_ids = [
                    str(channel_id) for channel_id in salesoffice_ids_queryset
                ]

                # Query the database to retrieve business units with associated companies
                business_units_with_companies = BusinessUnits.objects.annotate(
                    num_company=Count("company_master")
                ).filter(num_company__gt=0)

                # Extract the IDs from the queryset and store them as strings in the list
                business_unit_ids = [
                    str(business_unit.id)
                    for business_unit in business_units_with_companies
                ]
                # Create m2m_fields dictionary
                m2m_fields = {
                    "scgp_bu_ids": business_unit_ids,
                    "scgp_sales_organization_ids": sales_organization_ids,
                    "scgp_sales_group_ids": sales_group_ids,
                    "scgp_distribution_channel_ids": distribution_channel_ids,
                    "scgp_division_ids": divisionaster_ids,
                    "scgp_sales_office_ids": salesoffice_ids,
                }

                # Call handler_user_m2m_fields to handle m2m fields
                handler_user_m2m_fields(user_extended, m2m_fields)

                # Save the superuser
                super_user.save()

        except Exception as e:
            # Handle the exception here
            print(f"An error occurred: {str(e)}")
            # Rollback the transaction
            transaction.rollback()

        return super_user

    def customers(self):
        orders = Order.objects.values("user_id")
        return self.get_queryset().filter(
            Q(is_staff=False)
            | (Q(is_staff=True) & (Exists(orders.filter(user_id=OuterRef("pk")))))
        )

    def staff(self):
        return self.get_queryset().filter(is_staff=True)

    # Handle soft delete for user
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(Q(scgp_user__is_deleted=False) | Q(scgp_user__isnull=True))
        )


class Company(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)


class Office(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    company = models.ForeignKey(
        Company, blank=True, null=True, on_delete=models.SET_NULL
    )


class Division(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    company = models.ForeignKey(
        Company, blank=True, null=True, on_delete=models.SET_NULL
    )
    office = models.ForeignKey(Office, blank=True, null=True, on_delete=models.SET_NULL)


class User(PermissionsMixin, ModelWithMetadata, AbstractBaseUser):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=256, blank=True)
    last_name = models.CharField(max_length=256, blank=True)
    addresses = models.ManyToManyField(
        Address, blank=True, related_name="user_addresses"
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    note = models.TextField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    default_shipping_address = models.ForeignKey(
        Address, related_name="+", null=True, blank=True, on_delete=models.SET_NULL
    )
    default_billing_address = models.ForeignKey(
        Address, related_name="+", null=True, blank=True, on_delete=models.SET_NULL
    )
    avatar = VersatileImageField(upload_to="user-avatars", blank=True, null=True)
    jwt_token_key = models.CharField(max_length=12, default=get_random_string)
    language_code = models.CharField(
        max_length=35, choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE
    )
    search_document = models.TextField(blank=True, default="")

    company = models.ForeignKey(
        Company, on_delete=models.SET_NULL, blank=True, null=True
    )
    office = models.ForeignKey(Office, on_delete=models.SET_NULL, blank=True, null=True)
    distribution_channel = models.ForeignKey(
        Channel, on_delete=models.SET_NULL, blank=True, null=True
    )
    division = models.ForeignKey(
        Division, on_delete=models.SET_NULL, blank=True, null=True
    )

    USERNAME_FIELD = "email"

    objects = UserManager()

    class Meta:
        ordering = ("email",)
        permissions = (
            (AccountPermissions.MANAGE_USERS.codename, "Manage customers."),
            (AccountPermissions.MANAGE_STAFF.codename, "Manage staff."),
            (AccountPermissions.IMPERSONATE_USER.codename, "Impersonate user."),
        )
        indexes = [
            *ModelWithMetadata.Meta.indexes,
            # Orders searching index
            GinIndex(
                name="order_user_search_gin",
                # `opclasses` and `fields` should be the same length
                fields=["email", "first_name", "last_name"],
                opclasses=["gin_trgm_ops"] * 3,
            ),
            # Account searching index
            GinIndex(
                name="user_search_gin",
                # `opclasses` and `fields` should be the same length
                fields=["search_document"],
                opclasses=["gin_trgm_ops"],
            ),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._effective_permissions = None

    @property
    def effective_permissions(self) -> "QuerySet[Permission]":
        if self._effective_permissions is None:
            self._effective_permissions = get_permissions()
            if not self.is_superuser:
                UserPermission = User.user_permissions.through
                user_permission_queryset = UserPermission.objects.filter(
                    user_id=self.pk
                ).values("permission_id")

                UserGroup = User.groups.through
                GroupPermission = Group.permissions.through
                user_group_queryset = UserGroup.objects.filter(user_id=self.pk).values(
                    "group_id"
                )
                group_permission_queryset = GroupPermission.objects.filter(
                    Exists(user_group_queryset.filter(group_id=OuterRef("group_id")))
                ).values("permission_id")

                self._effective_permissions = self._effective_permissions.filter(
                    Q(
                        Exists(
                            user_permission_queryset.filter(
                                permission_id=OuterRef("pk")
                            )
                        )
                    )
                    | Q(
                        Exists(
                            group_permission_queryset.filter(
                                permission_id=OuterRef("pk")
                            )
                        )
                    )
                )
        return self._effective_permissions

    @effective_permissions.setter
    def effective_permissions(self, value: "QuerySet[Permission]"):
        self._effective_permissions = value
        # Drop cache for authentication backend
        self._effective_permissions_cache = None

    def get_full_name(self):
        if self.first_name or self.last_name:
            return ("%s %s" % (self.first_name, self.last_name)).strip()
        if self.default_billing_address:
            first_name = self.default_billing_address.first_name
            last_name = self.default_billing_address.last_name
            if first_name or last_name:
                return ("%s %s" % (first_name, last_name)).strip()
        return self.email

    def get_short_name(self):
        return self.email

    def has_perm(self, perm: Union[BasePermissionEnum, str], obj=None):  # type: ignore
        # This method is overridden to accept perm as BasePermissionEnum
        perm = perm.value if hasattr(perm, "value") else perm  # type: ignore

        # Active superusers have all permissions.
        if self.is_active and self.is_superuser and not self._effective_permissions:
            return True
        return _user_has_perm(self, perm, obj)


class CustomerNote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL
    )
    date = models.DateTimeField(db_index=True, auto_now_add=True)
    content = models.TextField()
    is_public = models.BooleanField(default=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="notes", on_delete=models.CASCADE
    )

    class Meta:
        ordering = ("date",)


class CustomerEvent(models.Model):
    """Model used to store events that happened during the customer lifecycle."""

    date = models.DateTimeField(default=timezone.now, editable=False)
    type = models.CharField(
        max_length=255,
        choices=[
            (type_name.upper(), type_name) for type_name, _ in CustomerEvents.CHOICES
        ],
    )
    order = models.ForeignKey("order.Order", on_delete=models.SET_NULL, null=True)
    parameters = JSONField(blank=True, default=dict, encoder=CustomJsonEncoder)
    user = models.ForeignKey(
        User, related_name="events", on_delete=models.CASCADE, null=True
    )
    app = models.ForeignKey(App, related_name="+", on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ("date",)

    def __repr__(self):
        return f"{self.__class__.__name__}(type={self.type!r}, user={self.user!r})"


class StaffNotificationRecipient(models.Model):
    user = models.OneToOneField(
        User,
        related_name="staff_notification",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    staff_email = models.EmailField(unique=True, blank=True, null=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("staff_email",)

    def get_email(self):
        return self.user.email if self.user else self.staff_email
