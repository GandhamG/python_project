from sap_master_data.models import BomMaterial


class BomMaterialRepo:
    @classmethod
    def get_bom_mat_by_parent_material_code_and_date(cls, parent_material_code, date):
        return BomMaterial.objects.filter(
            parent_material_code=parent_material_code,
            valid_from__lte=date,
            valid_to__gte=date,
        )

    @classmethod
    def get_bom_unit_quantity(cls, parent_material_code, material_code):
        return (
            BomMaterial.objects.filter(
                parent_material_code=parent_material_code, material_code=material_code
            )
            .values_list("quantity", flat=True)
            .first()
        )
