import re
from datetime import timedelta
from saleor.account.models import User
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from scgp_user_management.models import ScgUserOldPassword, ScgpUser

EMAIL_REGEX = "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$"
ID_REGEX = "\d{1,10}"
PASSWORD_REGEX = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d\w\W]{8,}$"


def check_exist_ad_user(ad_user: str) -> bool:
    scgp_user = ScgpUser.objects.filter(ad_user__iexact=ad_user)
    if not scgp_user:
        return False
    return True


def check_valid_email(email: str) -> bool:
    if not (re.search(EMAIL_REGEX, email)):
        return False
    return True


def check_external_email(email: str) -> bool:
    if email[-7:].lower() == "scg.com":
        return False
    return True


def check_email_exist(email: str) -> bool:
    exist_user = User.objects.filter(email=email.lower())
    if exist_user:
        return False
    return True


def check_valid_id(string: str) -> bool:
    if len(string) <= 10 and re.match(ID_REGEX, string):
        return True
    return False


def check_valid_password(password: str) -> bool:
    if not (re.match(PASSWORD_REGEX, password)):
        return False
    return True


def check_new_password_cannot_same_old_password(new_password, user):
    user_old_passwords = ScgUserOldPassword.objects.filter(user=user).order_by('-id')[:4]
    for user_old_password in user_old_passwords:
        if check_password(new_password, user_old_password.password):
            return True
    return False


def check_limit_reset_password(user, limit_time):
    user_old_password = ScgUserOldPassword.objects.filter(user=user).order_by('-id').first()
    if user_old_password:
        if user_old_password.created_at + timedelta(minutes=int(limit_time)) < timezone.now():
            return True
        else:
            return False
    return True
