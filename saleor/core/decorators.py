from typing import Callable

from django.http import HttpRequest, JsonResponse

from saleor.settings import INTERNAL_TOKEN


def request_method(method: str):
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            request: HttpRequest = args[0]
            if request.method.upper() != method.upper():
                return JsonResponse(
                    data={"message": "Method not allowed", "success": False}
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_internal_token(func: Callable):
    def wrapper(*args, **kwargs):
        request: HttpRequest = args[0]
        token = request.headers.get("SCG-Internal-Token", None)
        if not token or token != INTERNAL_TOKEN:
            return JsonResponse(
                {
                    "message": "Internal token missing or mismatch from request",
                    "success": False,
                }
            )
        return func(*args, **kwargs)

    return wrapper
