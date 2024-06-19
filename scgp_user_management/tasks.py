import logging

import requests

from saleor.celeryconf import app
from saleor.plugins.manager import get_plugins_manager
from sap_migration.models import Cart
from scgp_user_management.graphql.helpers import fullname_parse
from scgp_user_management.models import ScgpUser

TOKEN_URL = "https://scgp-gdc-api-dev.azurewebsites.net/api/token"
USER_DATA_URL = "https://scgp-gdc-apiother-dev.azurewebsites.net/Api/GDCEmployeeInfo/EmployeeInfoByADUser"


def get_gdc_access_key(application_id, secret_key):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "ApplicationId": application_id,
        "SecretKey": secret_key,
    }
    data = {"grant_type": "password"}
    response = requests.get(TOKEN_URL, headers=headers, data=data).json()
    return response.get("access_token", None)


def get_gdc_user_data(access_key, username):
    data = {"username": username, "referenceToken": access_key}
    response = requests.post(USER_DATA_URL, json=data).json()
    try:
        return response["responseData"][0]
    except IndexError:
        return None


def get_dgc_auths():
    manager = get_plugins_manager()
    _plugin = manager.get_plugin("scg.gdc")
    config = _plugin.config
    return config.application_id, config.secret_key


@app.task
def map_gdc_users():
    try:
        application_id, secret_key = get_dgc_auths()
        access_token = get_gdc_access_key(application_id, secret_key)

        scgp_users = ScgpUser.objects.exclude(ad_user__isnull=True).exclude(
            ad_user__exact=""
        )
        print("Start mapping GDC users")
        for scgp_user in list(scgp_users):
            ad_user = scgp_user.ad_user
            user_datas = get_gdc_user_data(access_token, ad_user)
            if not user_datas:
                continue
            first_name, last_name = fullname_parse(user_datas["e_FullName"])
            email = user_datas["email"] or f"{ad_user}@scgp.mock"
            scgp_user.user.first_name = first_name
            scgp_user.user.last_name = last_name
            scgp_user.user.email = email
            scgp_user.save()
            scgp_user.user.save()

            # Temporary disable base on data issue, need to confirm later
            # company_code = user_datas["companyCode"]
            # sale_org_ids = get_sale_orgs_by_code(company_code)
            # scgp_user.scgp_sales_organizations.set(sale_org_ids)
            #
            # bus = get_bus_from_sale_orgs(sale_org_ids)
            # scgp_user.scgp_bus.set(bus)
    except Exception as e:
        logging.error("Error when map gdc users: %s", e)


@app.task
def clear_cart():
    Cart.objects.all().delete()
