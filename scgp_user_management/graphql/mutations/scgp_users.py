import logging
from smtplib import SMTPDataError
from typing import Optional

import graphene
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group as GroupModel
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.middleware.csrf import _get_new_csrf_token
from django.utils import timezone

from saleor.account.models import User as UserModel
from saleor.core.jwt import create_access_token, create_refresh_token
from saleor.core.permissions import AccountPermissions
from saleor.graphql.account.mutations.authentication import CreateToken
from saleor.graphql.core.mutations import BaseMutation, ModelMutation
from saleor.graphql.core.types import AccountError, Upload

from scgp_user_management import models
from scgp_user_management.error_codes import ScgpUserManagementErrorCode
from scgp_user_management.graphql.data_import import scgp_user_mapping_data
from scgp_user_management.graphql.enums import ScgpCustomerType, ScgpUserStatus
from scgp_user_management.graphql.helpers import (
    get_scgp_require_fields,
    scgp_user_mapping_fields,
    raise_validation_error, is_customer_group,
)
from scgp_user_management.graphql.ScgpUserManagementError import ScgpUserManagementError
from scgp_user_management.graphql.types import ScgpUser
from scgp_user_management.graphql.validators import (
    check_email_exist,
    check_exist_ad_user,
    check_external_email,
    check_limit_reset_password,
    check_new_password_cannot_same_old_password,
    check_valid_email,
    check_valid_id,
    check_valid_password,
)
from scgp_user_management.implementations.scgp_users import (
    scgp_user_create,
    scgp_user_update,
    check_user_lock,
    check_wrong_user_password,
    scgp_delete_user,
)
from scgp_user_management.models import ParentGroup

logger = logging.getLogger(__name__)

PLUGIN_EMAIL = "scg.email"
GDC_PLUGIN = "scg.gdc"


class ScgpUserRegisterInput(graphene.InputObjectType):
    # Group in design
    user_parent_group_id = graphene.ID(required=True, description="ID of user group.")
    email = graphene.String(description="Email of user", required=True)
    first_name = graphene.String(description="First name of user.", required=True)
    last_name = graphene.String(description="Last name of user.", required=True)
    # Roles in design
    group_ids = graphene.List(
        graphene.ID, description="ID of user roles.", required=True
    )

    ad_user = graphene.String(description="Ad user.")
    sale_id = graphene.String(description="Id of sale.")
    employee_id = graphene.String(description="Id of employee.")

    scgp_bu_ids = graphene.List(graphene.ID, description="Business Unit of user.")
    scgp_sales_organization_ids = graphene.List(
        graphene.ID, description="Sales Organization of user."
    )
    scgp_sales_group_ids = graphene.List(
        graphene.ID, description="Sales Group of user."
    )
    scgp_distribution_channel_ids = graphene.List(
        graphene.ID, description="Distribution Channel of user."
    )
    scgp_division_ids = graphene.List(graphene.ID, description="Division of user.")
    scgp_sales_office_ids = graphene.List(
        graphene.ID, description="Sales Office of user."
    )

    customer_type = graphene.Field(ScgpCustomerType, description="Type of customer.")
    company_email = graphene.String(description="Email of company.")
    sold_to_ids = graphene.List(graphene.ID, description="ID of sold to.")
    display_name = graphene.String(description="Display name of user.")
    sap_id = graphene.String( description="sap id of user.")

class ScgpUserRegister(ModelMutation):
    class Arguments:
        input = ScgpUserRegisterInput(
            required=True, description="Fields required to register new user."
        )

    class Meta:
        description = "Scgp User Register"
        model = UserModel
        object_type = ScgpUser
        error_type_class = ScgpUserManagementError
        error_type_field = "cognito_errors"

    @classmethod
    def _handle_user_group(cls, data, user):
        user_parent_group_id = data.get("user_parent_group_id", False)
        if not user_parent_group_id:
            raise_validation_error("user_parent_group_id", "Group is required!")
        if user:
            old_parent_group_id = user.scgp_user.user_parent_group.id
            user_parent_group = ParentGroup.objects.filter(id=user_parent_group_id).first()
            if str(old_parent_group_id) != str(user_parent_group_id) and (is_customer_group(user_parent_group_id)
                                                                          or is_customer_group(old_parent_group_id)):
                raise_validation_error("user_parent_group_id", "Cannot change user group from or to Customer group!")

        # Make sure that only groups in parent can be import
        input_group_ids = data["group_ids"]
        group_ids = list(
            GroupModel.objects.filter(
                id__in=input_group_ids, parent_groups__id=user_parent_group_id
            ).values_list("id", flat=True)
        )
        if not group_ids:
            raise_validation_error("group_ids", "Role is required!")
        return user_parent_group_id, group_ids

    @classmethod
    def clean_input(cls, info, data, user=None):
        # Mapping base fields
        input_data = {
            "user_parent_group_id": (cls._handle_user_group(data, user))[0],
            "group_ids": (cls._handle_user_group(data, user))[1],
        }

        user_parent_group_id = input_data["user_parent_group_id"]
        user_parent_group = models.ParentGroup.objects.get(id=user_parent_group_id)
        user_parent_group_name = user_parent_group.name
        require_fields = get_scgp_require_fields(user_parent_group_name)
        mapping_fields = scgp_user_mapping_fields(data, require_fields)

        ad_user = data.get("ad_user", False)
        if (user_parent_group_name != "Customer") or \
                (user_parent_group_name == "Customer" and data.get("customer_type", False) == "Internal"):
            if not ad_user:
                raise_validation_error("ad_user", "AD User is required!")
            if not user and check_exist_ad_user(ad_user):
                raise_validation_error("ad_user", "มี Account นี้ในระบบแล้ว กรุณาลบ Account เก่าก่อนการสร้างใหม่")
            input_data["ad_user"] = ad_user

        email = data["email"]
        if (user and user.email != email) or not user:
            if not check_email_exist(email):
                raise_validation_error("email", f"Email {email} has been used!")

        sale_id = mapping_fields.get("sale_id", False)
        if sale_id:
            if not check_valid_id(sale_id):
                raise_validation_error("sale_id", "Sales ID format is not correct, please try input again")

        input_data = {
            **input_data,
            **mapping_fields,
            "email": mapping_fields["email"].lower(),
        }
        return input_data, user_parent_group

    @classmethod
    def send_email_handler(cls, info, user):
        email = user.email
        if user and not user.last_login and check_external_email(email):
            token = default_token_generator.make_token(user)
            manager = info.context.plugins
            manager.scgp_user_send_welcome_mail(
                "scg.email", email, token, "Your account has been created successfully", "reset_password.html"
            )
            models.ScgpUserTokenResetPassword.objects.filter(user=user).delete()
            models.ScgpUserTokenResetPassword.objects.create(
                user=user,
                token=token,
            )

    @classmethod
    def perform_mutation(cls, root, info, **data):
        data = data["input"]
        cleaned_data, user_parent_group = cls.clean_input(info, data)

        current_user = info.context.user
        if not current_user:
            raise ValidationError("Need login to update user")

        created_user = scgp_user_create(
            input_data=cleaned_data,
            current_user=current_user,
            user_parent_group=user_parent_group,
        )
        try:
            cls.send_email_handler(info, created_user)
        except SMTPDataError as e:
            logger.warning(e)
        return cls.success_response(created_user)


class ScgpUserUpdateInput(ScgpUserRegisterInput):
    is_active = graphene.Boolean(required=True, description="Set user active status")


class ScgpUserUpdate(ScgpUserRegister):
    class Arguments:
        id = graphene.ID(description="ID of an user to update.", required=True)
        input = ScgpUserUpdateInput(
            required=True, description="Fields required to update new user."
        )

    class Meta:
        description = "Scgp User Update"
        model = UserModel
        object_type = ScgpUser
        error_type_class = ScgpUserManagementError
        error_type_field = "cognito_errors"

    @classmethod
    def clean_input(cls, info, data, user):
        input_data, user_parent_group = super().clean_input(info, data, user)
        input_data["is_active"] = data.get("is_active", True)
        return input_data, user_parent_group

    @classmethod
    def perform_mutation(cls, root, info, **data):
        user_id = data["id"]
        user = UserModel.objects.get(pk=user_id)

        data = data["input"]
        cleaned_data, user_parent_group = cls.clean_input(info, data, user)

        current_user = info.context.user
        if not current_user:
            raise ValidationError("Need login to update user")

        updated_user = scgp_user_update(
            user=user,
            input_data=cleaned_data,
            user_parent_group=user_parent_group,
            current_user=current_user,
        )

        return cls.success_response(updated_user)


class ChangeScgpUserStatus(ModelMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of user to change status")
        status = graphene.Boolean(required=True, description="status want to change")

    class Meta:
        description = "Change Scgp User Status"
        model = UserModel
        object_type = ScgpUser
        error_type_class = ScgpUserManagementError
        error_type_field = "cognito_errors"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        id = data["id"]
        status = data["status"]
        try:
            user = models.User.objects.get(pk=id)
        except Exception as e:
            raise e

        user.scgp_user.updated_by = info.context.user
        user.is_active = status
        user.scgp_user.updated_at = timezone.now()
        user.save()
        user.scgp_user.save()

        return cls.success_response(user)


class ScgpUserCheckValidTokenResetPassword(BaseMutation):
    email = graphene.String(description="Email of reset password")
    token = graphene.String(description="Token of reset password")

    class Arguments:
        email = graphene.String(required=True, description="Email of reset password")
        token = graphene.String(required=True, description="Token of reset password")

    class Meta:
        description = "Scgp User Check Valid Token Reset Password"
        error_type_class = ScgpUserManagementError
        error_type_field = "user_check_valid_token_reset_password_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        token = data["token"]
        email = data["email"]
        if not check_valid_email(email):
            raise ValidationError({"email": ValidationError("Invalid Email format")})
        if check_email_exist(email):
            raise ValidationError(
                {
                    "email": ValidationError(
                        f"Email {email} don't exist",
                        ScgpUserManagementErrorCode.NOT_FOUND,
                    )
                }
            )
        manager = info.context.plugins
        valid_token = manager.scgp_user_check_valid_token_reset_password(
            PLUGIN_EMAIL, email, token
        )
        if not valid_token:
            raise ValidationError({"token": ValidationError("Invalid token")})
        return cls(errors=[], email=email, token=token)


class ScgpUserSendMailResetPassword(BaseMutation):
    message = graphene.String(description="message send mail reset password")

    class Arguments:
        email = graphene.String(required=True, description="Email of user")

    class Meta:
        description = "Scgp User Send Mail Reset Password"
        error_type_class = ScgpUserManagementError
        error_type_field = "user_send_mail_reset_password_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        email = data["email"]
        if not check_valid_email(email):
            raise ValidationError({"email": ValidationError("Invalid Email format")})
        if not check_external_email(email):
            raise ValidationError(
                {"email": ValidationError("Cannot input internal email.")}
            )

        if check_email_exist(email):
            return cls(errors=[], message="Send mail successfully")

        user = models.User.objects.get(email=email)
        token = default_token_generator.make_token(user)
        manager = info.context.plugins
        manager.scgp_user_send_reset_mail(
            PLUGIN_EMAIL, email, token, "Reset Password", "reset_password.html"
        )
        user = models.User.objects.filter(email=email).first()
        models.ScgpUserTokenResetPassword.objects.filter(user=user).delete()
        models.ScgpUserTokenResetPassword.objects.create(
            user=user,
            token=token,
        )
        return cls(errors=[], message="Send mail successfully")


class ScgpUserConfirmResetPassword(BaseMutation):
    message = graphene.String(description="message of confirm forgot password")

    class Arguments:
        email = graphene.String(required=True, description="Email of user")
        new_password = graphene.String(
            required=True, description="New Password of user"
        )
        confirm_password = graphene.String(
            required=True, description="Confirm Password of user"
        )
        token = graphene.String(required=True, description="token of user")

    class Meta:
        description = "Scgp User Confirm Reset Password"
        model = UserModel
        object_type = ScgpUser
        error_type_class = ScgpUserManagementError
        error_type_field = "user_confirm_reset_password"

    @classmethod
    def clean_input(cls, info, data):
        email = data["email"]
        new_password = data["new_password"]
        confirm_password = data["confirm_password"]
        token = data["token"]
        if not check_valid_email(email):
            raise ValidationError({"email": ValidationError("Invalid Email format")})
        if check_email_exist(email):
            raise ValidationError(
                {
                    "email": ValidationError(
                        f"Email {email} don't exist",
                        ScgpUserManagementErrorCode.NOT_FOUND,
                    )
                }
            )
        if not check_valid_password(new_password):
            raise ValidationError(
                {
                    "password": ValidationError(
                        "New Password format is not correct, please try input again"
                    )
                }
            )
        if not check_valid_password(confirm_password):
            raise ValidationError(
                {
                    "confirm_password": ValidationError(
                        "Confirm Password format is not correct, please try input again"
                    )
                }
            )
        if new_password != confirm_password:
            raise ValidationError(
                {
                    "confirm_password": ValidationError(
                        "Confirm new password don't seem to match"
                    )
                }
            )
        manager = info.context.plugins
        valid_token = manager.scgp_user_check_valid_token_reset_password(
            PLUGIN_EMAIL, email, token
        )
        if not valid_token:
            raise ValidationError({"token": ValidationError("Invalid token")})
        user = models.User.objects.filter(Q(email=email) | Q(scgp_user__username=email)).first()
        limit_time = manager.scgp_user_limit_time_out_reset_password(PLUGIN_EMAIL)
        if not check_limit_reset_password(user, limit_time):
            raise ValidationError(
                {
                    "limit_reset_password": ValidationError(
                        "Not allow to change password in case there is a previous "
                        "change within past 10 minutes",
                        ScgpUserManagementErrorCode.NOT_ALLOW,
                    )
                }
            )
        if check_new_password_cannot_same_old_password(new_password, user):
            raise ValidationError(
                {
                    "password": ValidationError(
                        "Your new password cannot be the same as your old password."
                    )
                }
            )
        return email, new_password, token, user

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        email, new_password, token, user = cls.clean_input(info, data)
        user.password = make_password(new_password)
        if not user.last_login:
            user.last_login = timezone.now()
        user.save()
        models.ScgUserOldPassword.objects.create(
            user=user, password=make_password(new_password)
        )
        models.ScgpUserTokenResetPassword.objects.filter(user=user).delete()
        scgp_user = models.ScgpUser.objects.filter(user=user).first()
        if scgp_user is not None:
            scgp_user.time_lock = None
            scgp_user.password_wrong = 0
            scgp_user.save()
        return cls(errors=[], message="Reset password successfully")


class ScgpUserLogin(CreateToken):
    message = graphene.String(description="Use login status message.")
    status = graphene.Field(ScgpUserStatus, description="User login status.")
    temp_token = graphene.String(description="User token for first login.")
    username = graphene.String(description="Username.")

    class Arguments:
        email = graphene.String(
            required=True, description="Email or username of a user."
        )
        password = graphene.String(required=True, description="Password of a user.")

    class Meta:
        description = "Create JWT token."
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def _retrieve_user_from_credentials(cls, email, password) -> Optional[models.User]:
        user = UserModel.objects.filter(
            Q(email=email) | Q(scgp_user__username=email)
        ).first()
        if user and user.check_password(password):
            return user
        return None

    @classmethod
    def validate_data(cls, info, data):
        email = data["email"]
        if not check_external_email(email):
            raise ValidationError("Please use personal email to login")

    @classmethod
    def first_login_handler(cls, info, data, user):
        if not user.last_login:
            status = (ScgpUserStatus.FORCE_CHANGE_PASSWORD,)
            message = (ScgpUserStatus.FORCE_CHANGE_PASSWORD.value,)
        elif not user.email or user.email[-9:] == "scgp.mock":
            status = (ScgpUserStatus.FORCE_ADD_EMAIL,)
            message = (ScgpUserStatus.FORCE_ADD_EMAIL.value,)

        token = default_token_generator.make_token(user)
        models.ScgpUserTokenResetPassword.objects.filter(user=user).delete()
        models.ScgpUserTokenResetPassword.objects.create(
            user=user,
            token=token,
        )
        return cls(
            message=message[0],
            status=status[0],
            username=user.scgp_user.username,
            temp_token=token,
        )

    @classmethod
    def perform_mutation(cls, root, info, **data):
        data["email"] = data["email"].lower()
        cls.validate_data(info, data)
        manager = info.context.plugins
        wrong_password_number = manager.scgp_user_wrong_password_number(PLUGIN_EMAIL)
        time_lock_user = manager.scgp_user_time_lock_user(PLUGIN_EMAIL)
        user_lock = check_user_lock(data["email"], time_lock_user)
        if user_lock:
            raise ValidationError(
                {"password": ValidationError("บัญชีของคุณถูกล็อคชั่วคราว กรุณารอสักครู่ เพื่อใส่รหัสผ่านใหม่อีกครั้ง")})
        else:
            check_wrong_user_password(data["email"], data["password"], wrong_password_number)
        user = cls.get_user(info, data)

        if not user.is_superuser and (
                not user.last_login or not user.email or user.email[-9:] == "scgp.mock"
        ):
            return cls.first_login_handler(info, data, user)
        return super().perform_mutation(root, info, **data)


class ScgpUserFirstLoginUpdate(ScgpUserLogin):
    class Arguments:
        password = graphene.String(description="New password for current user.")
        confirm_password = graphene.String(description="Confirm password.")
        email = graphene.String(description="New email for current user.")
        username = graphene.String(required=True, description="Username to update.")
        temp_token = graphene.String(required=True, description="Token of a user.")

    class Meta:
        description = "Create JWT token."
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def validate_data(cls, info, data):
        token = data["temp_token"]
        manager = info.context.plugins
        valid_token = manager.scgp_user_check_valid_token_reset_password(
            PLUGIN_EMAIL, data["username"], token
        )
        if not valid_token:
            raise ValidationError({"temp_token": ValidationError("Invalid token")})

        if not data.get("password", "") and not data.get("email", ""):
            raise ValidationError(
                "Please enter password or email to update.",
                ScgpUserManagementErrorCode.REQUIRED,
            )

        password = data.get("password", "")
        confirm_password = data.get("confirm_password", "")
        if password != confirm_password:
            raise ValidationError(
                {
                    "confirm_password": ValidationError(
                        "Confirm new password don't seem to match"
                    )
                }
            )
        if password and not check_valid_password(password):
            raise ValidationError(
                {
                    "password": ValidationError(
                        "New Password format is not correct, please try input again"
                    )
                }
            )

        email = data.get("email", "")
        if email:
            if not check_valid_email(email):
                raise ValidationError(
                    {
                        "email": ValidationError(
                            "Invalid email format."
                        )
                    }
                )
            if not check_external_email(email):
                raise ValidationError(
                    {
                        "email": ValidationError(
                            "Can not use internal email."
                        )
                    }
                )
            if not check_email_exist(email):
                raise ValidationError(
                    {
                        "email": ValidationError(
                            "This email has already been used. Please try another."
                        )
                    }
                )

        return data

    @classmethod
    def __update_user_data(cls, info, data, user):
        password = data.get("password", "")
        email = data.get("email", "").lower()
        if password:
            if user.check_password(password):
                raise ValidationError(
                    {
                        "password": ValidationError(
                            "Your new password cannot be the same as your old password."
                        )
                    }
                )
            user.password = make_password(password)
            user.last_login = timezone.now()
            if password:
                models.ScgUserOldPassword.objects.create(
                    user=user, password=make_password(password)
                )
        if email:
            user.email = email
        user.scgp_user.updated_at = timezone.now()
        user.save()

    @classmethod
    def _finish_return(cls, info, data, user):
        access_token = create_access_token(user)
        csrf_token = _get_new_csrf_token()
        refresh_token = create_refresh_token(user, {"csrfToken": csrf_token})
        info.context.refresh_token = refresh_token
        info.context._cached_user = user
        user.last_login = timezone.now()
        user.save(update_fields=["last_login", "updated_at"])
        return cls(
            errors=[],
            user=user,
            token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
        )

    @classmethod
    def perform_mutation(cls, root, info, **data):
        data = cls.validate_data(info, data)
        username = data["username"]
        user = UserModel.objects.filter(
            Q(email=username) | Q(scgp_user__username=username)
        ).first()
        if not user:
            raise ValidationError(
                "User not found.", ScgpUserManagementErrorCode.NOT_FOUND
            )
        cls.__update_user_data(info, data, user)

        if not user.last_login or not user.email or user.email[-9:] == "scgp.mock":
            return super().first_login_handler(info, data, user)

        models.ScgpUserTokenResetPassword.objects.filter(user=user).delete()
        return cls._finish_return(info, data, user)


class ScgpUserMappingData(BaseMutation):
    status = graphene.String()

    class Arguments:
        file = Upload(
            required=True, description="Represents a file in a multipart request."
        )

    class Meta:
        description = "Mapping scgp user data"
        error_type_class = AccountError
        error_type_field = "upload_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        file_data = info.context.FILES.get(data["file"])
        user = info.context.user
        status = scgp_user_mapping_data(file_data, user)

        return cls(status=status)


class ScgpDeleteUser(BaseMutation):
    status = graphene.String()

    class Arguments:
        user_id = graphene.ID(description="User ID to delete.", required=True)

    class Meta:
        description = "Delete User"
        error_type_class = AccountError
        error_type_field = "upload_errors"
        permissions = (AccountPermissions.MANAGE_STAFF,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        user_id = data.get("user_id")
        user = UserModel.objects.get(pk=user_id)
        current_user = info.context.user
        status = scgp_delete_user(user, current_user)
        return cls(status=status)
