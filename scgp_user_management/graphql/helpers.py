from django.core.exceptions import ValidationError
from django.db.models import Func

from sap_migration.models import (
    BusinessUnits,
    SalesOrganizationMaster,
)
from scgp_user_management.graphql.enums import (
    ScgpUserInputFields,
    ScgpSaleUserInputFields,
    ScgpCustomerUserInputFields,
    ScgpSectionUserInputFields,
)
from scgp_user_management.models import ParentGroup
from utils.enums import ParentGroupCode


def get_scgp_require_fields(parent_group_name):
    if parent_group_name in ["Sales"]:
        return ScgpSaleUserInputFields.EXTRA_FIELDS.value
    if parent_group_name in ["Section"]:
        return ScgpSectionUserInputFields.EXTRA_FIELDS.value
    if parent_group_name == "Customer":
        return ScgpCustomerUserInputFields.EXTRA_FIELDS.value
    return ScgpUserInputFields.EXTRA_FIELDS.value


def raise_validation_error(field, message):
    raise ValidationError({field: ValidationError(message)})


def scgp_user_mapping_fields(params, require_fields):
    input_data = {}
    for k, v in require_fields.items():
        require_value = params.get(k, None)
        if not require_value and k not in ("company_email", "display_name", "sap_id"):
            raise_validation_error(k, f"{v} is required!")
        if k in "sap_id" and require_value:
            input_data[k] = require_value.upper()
        else:
            input_data[k] = require_value
    return input_data


def fullname_parse(fullname):
    try:
        first_name, last_name = fullname.split(" ", 1)
        return first_name, last_name
    except ValueError:
        return fullname, fullname


def get_sale_orgs_by_code(code):
    sale_org_ids = SalesOrganizationMaster.objects.filter(code=code).values_list("id", flat=True)
    return list(sale_org_ids)


def get_bus_from_sale_orgs(sale_orgs):
    bu_ids_qs = BusinessUnits.objects.filter(
        salesorganizationmaster__id__in=sale_orgs
    ).values_list("id", flat=True).distinct()
    return list(bu_ids_qs)


def get_sale_orgs_from_gdc(code):
    sale_orgs = SalesOrganizationMaster.objects.filter(code=code)
    return sale_orgs


def get_bus_from_gdc_by_sale_orgs(sale_orgs):
    bus = BusinessUnits.objects.filter(salesorganizationmaster__in=sale_orgs)
    return bus


def thai_collage_field(field_name):
    """
    Only work with system has th_TH collation
    """
    return Func(
        field_name,
        function='th_TH',
        template='(%(expressions)s) COLLATE "%(function)s"',
    )


def is_customer_group(user_group_id):
    user_parent_group = ParentGroup.objects.filter(id=user_group_id).first()
    return ParentGroupCode.CUSTOMER.value == user_parent_group.code
