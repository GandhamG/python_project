from sap_master_data.models import MaterialPurchaseMaster


class MaterialPurchaseMasterRepo:
    @classmethod
    def get_mat_pur_master_by_material_code(cls, material_code):
        return MaterialPurchaseMaster.objects.filter(
            material_code=material_code
        ).distinct("plant_code")
