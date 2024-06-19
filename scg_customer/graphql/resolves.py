from django.contrib.auth import models as auth_models
from django.db.models import Exists

from saleor.account import models
from scg_checkout.models import Contract


def resolve_companies():
    return models.Company.objects.all()


def resolve_divisions():
    return models.Division.objects.all()


def resolve_offices():
    office = models.Office.objects.all()
    return office


def resolve_customer(info, id):
    customer = models.User.objects.filter(id=id).first()
    return customer


def resolve_auth_groups(info):
    auth_groups = auth_models.Group.objects.all()
    return auth_groups


def resolve_sale_groups(user_id):
    groups = auth_models.Group.objects.filter(user__in=[user_id])
    return groups


def resolve_contracted_customer(info, id):
    customer = (
        models.User.objects.filter(id=id)
        .filter(Exists(Contract.objects.filter(customer_id=id)))
        .first()
    )
    return customer
