from typing import Optional

from django.core.handlers.wsgi import WSGIRequest

SALEOR_AUTH_HEADER = "HTTP_AUTHORIZATION_BEARER"
DEFAULT_AUTH_HEADER = "HTTP_AUTHORIZATION"
AUTH_HEADER_PREFIXES = ["JWT", "BEARER"]


def get_token_from_request(request: WSGIRequest) -> Optional[str]:
    """
    Because save password function of browser auto add "Authorization-bearer" to header of request,
    But FE primary use "Authorization" header, so we prefer to use token in "Authorization" header
    """

    auth_token = None
    auth = request.META.get(DEFAULT_AUTH_HEADER, "").split(maxsplit=1)
    if len(auth) == 2 and auth[0].upper() in AUTH_HEADER_PREFIXES:
        auth_token = auth[1]

    if not auth_token:
        auth_token = request.META.get(SALEOR_AUTH_HEADER)

    return auth_token
