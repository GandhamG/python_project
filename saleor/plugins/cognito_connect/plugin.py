from dataclasses import dataclass
from typing import Optional

import boto3
import cognitojwt

from ..base_plugin import BasePlugin, ConfigurationTypeField
from . import PLUGIN_ID
from .dataclasses import CognitoConnectConfig

SERVICE = "cognito-idp"
REGION = "ap-southeast-1"


@dataclass
class ExternalCognitoUser:
    username: Optional[str] = None
    email: Optional[str] = None


class CognitoConnectPlugin(BasePlugin):
    PLUGIN_ID = PLUGIN_ID
    DEFAULT_CONFIGURATION = [
        {"name": "client_id", "value": None},
        {"name": "client_secret", "value": None},
        {"name": "enable_refresh_token", "value": True},
        {"name": "oauth_authorization_url", "value": None},
        {"name": "oauth_token_url", "value": None},
        {"name": "json_web_key_set_url", "value": None},
        {"name": "oauth_logout_url", "value": None},
        {"name": "user_info_url", "value": None},
        {"name": "audience", "value": None},
        {"name": "use_oauth_scope_permissions", "value": False},
        {"name": "user_pool_id", "value": None},
    ]
    PLUGIN_NAME = "Cognito Connect"
    CONFIGURATION_PER_CHANNEL = False

    CONFIG_STRUCTURE = {
        "client_id": {
            "type": ConfigurationTypeField.STRING,
            "help_text": (
                "Your Client ID required to authenticate on the provider side."
            ),
            "label": "Client ID",
        },
        "client_secret": {
            "type": ConfigurationTypeField.SECRET,
            "help_text": (
                "Your client secret required to authenticate on provider side."
            ),
            "label": "Client Secret",
        },
        "enable_refresh_token": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": (
                "Determine if the refresh token should be also fetched from provider. "
                "By disabling it, users will need to re-login after the access token "
                "expired. By enabling it, frontend apps will be able to refresh the "
                "access token. OAuth provider needs to have included scope "
                "`offline_access`."
            ),
            "label": "Enable refreshing token",
        },
        "oauth_authorization_url": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "The endpoint used to redirect user to authorization page.",
            "label": "OAuth Authorization URL",
        },
        "oauth_token_url": {
            "type": ConfigurationTypeField.STRING,
            "help_text": (
                "The endpoint to exchange an Authorization Code for a Token."
            ),
            "label": "OAuth Token URL",
        },
        "json_web_key_set_url": {
            "type": ConfigurationTypeField.STRING,
            "help_text": (
                "The JSON Web Key Set (JWKS) is a set of keys containing the public "
                "keys used to verify any JSON Web Token (JWT) issued by the "
                "authorization server and signed using the RS256 signing algorithm."
            ),
            "label": "JSON Web Key Set URL",
        },
        "oauth_logout_url": {
            "type": ConfigurationTypeField.STRING,
            "help_text": (
                "The URL for logging out the user from the OAuth provider side."
            ),
            "label": "OAuth logout URL",
        },
        "user_info_url": {
            "type": ConfigurationTypeField.STRING,
            "help_text": (
                "The URL which can be used to fetch user details by using an access "
                "token."
            ),
            "label": "User info URL",
        },
        "audience": {
            "type": ConfigurationTypeField.STRING,
            "help_text": (
                "The OAuth resource identifier. If provided, Saleor will define "
                "audience for each authorization request."
            ),
            "label": "Audience",
        },
        "use_oauth_scope_permissions": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": (
                "Use OAuth scope permissions to grant a logged-in user access to "
                "protected resources. Your OAuth provider needs to have defined "
                "Saleor's permission scopes in format saleor:<saleor-perm>. Check"
                " Saleor docs for more details."
            ),
            "label": "Use OAuth scope permissions",
        },
        "user_pool_id": {
            "type": ConfigurationTypeField.STRING,
            "help_text": ("Cognito User Pool ID"),
            "label": "Cognito User Pool ID",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert to dict to easier take config elements
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = CognitoConnectConfig(
            client_id=configuration["client_id"],
            client_secret=configuration["client_secret"],
            enable_refresh_token=configuration["enable_refresh_token"],
            json_web_key_set_url=configuration["json_web_key_set_url"],
            authorization_url=configuration["oauth_authorization_url"],
            token_url=configuration["oauth_token_url"],
            logout_url=configuration["oauth_logout_url"],
            audience=configuration["audience"],
            use_scope_permissions=configuration["use_oauth_scope_permissions"],
            user_info_url=configuration["user_info_url"],
            user_pool_id=configuration["user_pool_id"],
        )

        # Determine, if we have defined all fields required to use OAuth access token
        # as Saleor's authorization token.
        self.use_oauth_access_token = bool(
            self.config.user_info_url and self.config.json_web_key_set_url
        )

        # Determine, if we have defined all fields required to process the
        # authorization flow.
        self.use_authorization_flow = bool(
            self.config.json_web_key_set_url
            and self.config.authorization_url
            and self.config.token_url
        )

        # Setup client for boto3
        # self.client = boto3.client(SERVICE, region_name=REGION)
        self.client = boto3.client(
            SERVICE,
            region_name=REGION,
        )

    def extenal_access_cognito(self, data: dict, previous_value) -> ExternalCognitoUser:
        accessToken = data
        region = "ap-southeast-1"
        user_pool_id = self.config.user_pool_id
        # user_pool_id = "ap-southeast-1_fRdgJX0by"
        # app_client_id = "6vq4rfu5et98r5fuqq22gsgip7"

        try:
            verify_clams: dict = cognitojwt.decode(
                accessToken, region, user_pool_id, self.config.client_id, testmode=False
            )

            return ExternalCognitoUser(
                username=verify_clams.get("cognito:username", None),
                email=verify_clams.get("email", None),
            )
        except Exception:
            return None
