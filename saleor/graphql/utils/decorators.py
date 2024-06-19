from django.contrib.auth.models import AnonymousUser


def login_required(resolver):
    def inner(*args, **kwargs):
        info = args[1]
        if isinstance(info.context.user, AnonymousUser):
            return None
        return resolver(*args, **kwargs)

    return inner
