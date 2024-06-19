from sap_master_data.models import MaterialSaleMaster


class MaterialSaleMasterRepo:
    @classmethod
    def get_material_sale_master_by_material_code(
        cls, material_code, sales_organization, distribution_channel
    ):
        return MaterialSaleMaster.objects.filter(
            material_code=material_code,
            sales_organization_code=sales_organization,
            distribution_channel_code=distribution_channel,
        ).first()
