from sap_master_data.models import SoldToMaterialMaster


class SoldToMaterialMasterRepo:
    @classmethod
    def get_sold_to_material_by_material_code(cls, material_code):
        return SoldToMaterialMaster.objects.filter(material_code=material_code).first()

    @classmethod
    def get_sold_to_material_master_by_sale_org_dist_channel_sold_to(
        cls, sale_org, distribution_channel, sold_to
    ):
        qs = SoldToMaterialMaster.objects.filter(
            sales_organization_code=sale_org,
            distribution_channel_code=distribution_channel,
            sold_to_code=sold_to,
        ).distinct("material_code")
        return qs

    @classmethod
    def get_sold_to_material_by_sold_to_material_code(cls, sold_to_material_code):
        return SoldToMaterialMaster.objects.filter(
            sold_to_material_code=sold_to_material_code
        ).first()
