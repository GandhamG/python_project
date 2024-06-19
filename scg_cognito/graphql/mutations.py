import graphene
from django.middleware.csrf import _get_new_csrf_token
from django.utils import timezone
from django.core.exceptions import ValidationError

from saleor.account import models
from saleor.core.jwt import create_access_token, create_refresh_token
from saleor.graphql.account.types import User
from saleor.graphql.core.mutations import BaseMutation
from scgp_user_management.graphql.helpers import raise_validation_error
from scgp_user_management.models import ScgpUser

from .CognitoError import CognitoError
from .enums import CognitoErrorCode


class GenerateTokenFromCognito(BaseMutation):
    token = graphene.String(description="JWT token, required to authenticate.")
    refresh_token = graphene.String(
        description="JWT refresh token, required to re-generate access token."
    )
    csrf_token = graphene.String(
        description="CSRF token required to re-generate access token."
    )
    user = graphene.Field(User, description="A user instance.")

    class Arguments:
        idToken = graphene.String(required=True, description="JWT token to validate.")

    class Meta:
        description = "generate token from cognito"
        error_type_class = CognitoError
        error_type_field = "cognito_errors"

    @classmethod
    def __get_user(cls, access_tokens_response):
        email = access_tokens_response.email or access_tokens_response.username
        if not email:
            raise raise_validation_error("email", "ID Token error!")
        email = email.lower()

        user = models.User.objects.filter(
            email=email
        ).first()
        if not user:
            raise raise_validation_error(
                "scg_login_error",
                "Your account has no permission, please contact: (+66) 0 2555 6666",
            )
        return user

    @classmethod
    def perform_mutation(cls, root, info, **data):
        plugin_id = "scg.authentication.cognitoconnect"
        access_token = data.get("idToken")
        manager = info.context.plugins
        access_tokens_response = manager.extenal_access_cognito(plugin_id, access_token)
        if access_tokens_response is None:
            raise ValidationError(
                {
                    "idToken": ValidationError(
                        "Please, enter valid credentials",
                        code=CognitoErrorCode.INVALID_CREDENTIALS.value,
                    )
                }
            )
        user = cls.__get_user(access_tokens_response)
        token = create_access_token(user)
        csrf_token = _get_new_csrf_token()
        refresh_token = create_refresh_token(user, {"csrfToken": csrf_token})
        user.last_login = timezone.now()
        user.save(update_fields=["last_login", "updated_at"])
        return cls(
            errors=[],
            user=user,
            token=token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
        )
