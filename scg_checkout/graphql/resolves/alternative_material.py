import random

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction

from sap_migration.models import AlternateMaterialOs
from sap_migration import models as migration_models
from scg_checkout.error_codes import ContractCheckoutErrorCode
from scg_checkout.graphql.enums import AlternativeMaterialTypes
from sap_master_data import models as master_models
from scg_checkout.models import AlternativeMaterialLastUpdateBy

EDIT_ALT_MAT_MAPPING_NOT_FOUND = """
เนื่องจาก Material Master นี้ถูกลบออกจากระบบแล้ว
กรุณากลับไปหน้าค้นหา เพื่อเพิ่มหรือแก้ไขข้อมูล
""".strip()

DELETE_ALT_MAPPING_NOT_FOUND = """
เนื่องจาก Material Master นี้ถูกลบออกจากระบบแล้ว
""".strip()


def map_request_fields_by_type(params, require_fields):
    input_data = {}
    for field in require_fields:
        require_value = params.get(field, None)
        if not require_value:
            raise ValidationError(f"Field {field} is required!")
        input_data[field] = require_value
    return input_data


@transaction.atomic
def alternative_material_add(data, user):
    try:
        types = data["type"]
        if types == "Material":
            types = "M"
        if types == "Grade/Gram":
            types = None
        sale_organization_id = data["sale_organization_id"]
        sold_to_id = data["sold_to_id"]
        material_own_id = data["material_own_id"]
        lines = data["lines"]

        alternative_material = migration_models.AlternateMaterial.objects.create(
            created_by=user,
            updated_by=user,
            type=types,
            sales_organization_id=sale_organization_id,
            sold_to_id=sold_to_id,
            material_own_id=material_own_id,
        )

        last_update_by, created = AlternativeMaterialLastUpdateBy.objects.get_or_create(
            defaults={'updated_by': user}
        )
        if not created:
            last_update_by.updated_by = user
            last_update_by.save()

        alternative_material_os_lines = []

        for line in lines:
            material_os_id = line["material_os_id"]
            priority = line["priority"]

            # Get diameter or set default
            diameter = None if types == AlternativeMaterialTypes.MATERIAL.value \
                else line.get("dia").zfill(3)

            alternative_material_os_line = migration_models.AlternateMaterialOs(
                alternate_material=alternative_material,
                material_os_id=material_os_id,
                diameter=diameter,
                priority=priority,
            )

            alternative_material_os_lines.append(alternative_material_os_line)

        migration_models.AlternateMaterialOs.objects.bulk_create(alternative_material_os_lines)
        alternative_material.save()
        last_update_by.save()

        return alternative_material

    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def resolve_materials_os(alternative_material_id):
    return AlternateMaterialOs.objects.filter(
        alternate_material_id=alternative_material_id
    ).all()


@transaction.atomic
def delete_alternative_material_os(id, user):
    try:
        alternate_material_os = migration_models.AlternateMaterialOs.objects.filter(
            id=id
        ).first()

        if not alternate_material_os:
            raise ValidationError(
                {
                    "alternate_material_os_id": ValidationError(
                        DELETE_ALT_MAPPING_NOT_FOUND,
                        code=ContractCheckoutErrorCode.INVALID.value,
                    )
                }
            )

        priority = alternate_material_os.priority
        alternate_material_id = alternate_material_os.alternate_material_id
        alternate_material_oss_change = migration_models.AlternateMaterialOs.objects.filter(
            alternate_material_id=alternate_material_id, priority__gt=priority
        )

        alternate_material_oss_update = []

        for alternate_material_os_change in list(alternate_material_oss_change):
            priority_alternative_material_os = alternate_material_os_change.priority
            priority_alternative_material_os -= 1
            alternative_material_os_update = migration_models.AlternateMaterialOs(
                id=alternate_material_os_change.id, priority=priority_alternative_material_os
            )
            alternate_material_oss_update.append(alternative_material_os_update)

        if alternate_material_oss_update:
            migration_models.AlternateMaterialOs.objects.bulk_update(
                alternate_material_oss_update, ["priority"]
            )

        alternate_material_id = alternate_material_os.alternate_material.id
        alternate_material = migration_models.AlternateMaterial.objects.filter(
            id=alternate_material_id
        ).first()
        alternate_material.updated_by_id = user
        alternate_material.save()
        alternate_material_os.delete()
        alter_material_os = migration_models.AlternateMaterialOs.objects.filter(
            alternate_material_id=alternate_material_id) \
            .first()
        if not alter_material_os:
            alternate_material.delete()
        last_update_by = AlternativeMaterialLastUpdateBy.objects.first()
        if not last_update_by:
            last_update_by = AlternativeMaterialLastUpdateBy(
                updated_by=user
            )
        else:
            last_update_by.updated_by = user
        last_update_by.save()

        return True
    except Exception as e:
        transaction.set_rollback(True)
        raise e


def resolve_material_alter(qs):
    return master_models.MaterialMaster.objects.filter(material_code__in=qs)


@transaction.atomic
def edit_alternative_material(alternative_material_id, data, user):
    try:
        deleted_alternate_material_os_ids = migration_models.AlternateMaterialOs.objects.filter(
            alternate_material__id=alternative_material_id
        ).values_list("id", flat=True)

        if deleted_alternate_material_os_ids:
            for (
                    deleted_alternative_material_os_id
            ) in deleted_alternate_material_os_ids:
                alternative_material_os = migration_models.AlternateMaterialOs.objects.filter(
                    id=deleted_alternative_material_os_id,
                    alternate_material__id=alternative_material_id,
                ).first()

                if not alternative_material_os:
                    raise ValidationError(f"Alternated Material doesn't exist")

                alternative_material_os.delete()

        sale_organization_id = data["sale_organization_id"]
        sold_to_id = data["sold_to_id"]
        material_own_id = data["material_own_id"]
        lines = data["lines"]

        alternative_material = migration_models.AlternateMaterial.objects.filter(
            id=alternative_material_id
        ).first()
        alternative_material.sales_organization_id = sale_organization_id
        alternative_material.sold_to_id = sold_to_id
        alternative_material.updated_by_id = user
        alternative_material.material_own_id = material_own_id
        alternative_material.save()
        alternative_material_os_lines = []

        alternative_material_type = alternative_material.type

        for line in lines:
            material_os_id = line["material_os_id"]
            priority = line["priority"]

            # Get diameter or set default
            diameter = None if alternative_material_type == AlternativeMaterialTypes.MATERIAL.value \
                else line.get("dia").zfill(3)

            alternative_material_os_line = migration_models.AlternateMaterialOs(
                alternate_material=alternative_material,
                material_os_id=material_os_id,
                diameter=diameter,
                priority=priority,
            )
            alternative_material_os_lines.append(alternative_material_os_line)

        if alternative_material_os_lines:
            migration_models.AlternateMaterialOs.objects.bulk_create(
                alternative_material_os_lines
            )
        last_update_by = AlternativeMaterialLastUpdateBy.objects.first()
        last_update_by.updated_by = user
        last_update_by.save()

        return alternative_material
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def resolve_alternative_material(alternative_material_id):
    result = migration_models.AlternateMaterial.objects.filter(
        id=alternative_material_id
    ).first()
    return result


def resolve_last_update_date():
    result = AlternativeMaterialLastUpdateBy.objects.first()
    return result.updated_at if result else None


def resolve_alternative_materials():
    return migration_models.AlternateMaterial.objects.all()
