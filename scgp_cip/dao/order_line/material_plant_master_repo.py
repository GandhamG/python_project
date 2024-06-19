from sap_master_data.models import MaterialPlantMaster


class MaterialPlantMasterRepo:
    @classmethod
    def get_plant_codes_by_material_code(cls, material_code):
        return (
            MaterialPlantMaster.objects.filter(material_code=material_code)
            .values("plant_code")
            .distinct()
        )

    @classmethod
    def get_plant_code_by_material_code(cls, material_code):
        return (
            MaterialPlantMaster.objects.filter(material_code=material_code)
            .first()
            .plant_code
        )

    @classmethod
    def get_plant_by_material_code_and_plant(cls, material_code, plant):
        return MaterialPlantMaster.objects.filter(
            material_code=material_code, plant_code=plant
        ).first()
