from sap_master_data.models import Conversion2Master


class Conversion2MasterRepo:
    @classmethod
    def get_conversion_by_material_code(cls, material_code):
        return Conversion2Master.objects.filter(
            material_code=material_code, to_unit__isnull=False
        ).distinct("to_unit")

    @classmethod
    def get_conversion_by_material_code_and_tounit(cls, material_code, to_unit):
        return Conversion2Master.objects.filter(
            material_code=material_code, to_unit=to_unit
        ).first()
