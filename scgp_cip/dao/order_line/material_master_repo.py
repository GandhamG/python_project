from django.db.models import Subquery

from sap_master_data.models import MaterialMaster, MaterialSaleMaster
from scgp_cip.common.constants import STATUS_ACTIVE


class MaterialMasterRepo:
    @classmethod
    def get_material_by_material_code(cls, material_code):
        return MaterialMaster.objects.filter(material_code=material_code).first()

    @classmethod
    def get_material_master_by_sale_org_dist_channel(
        cls, sale_org, distribution_channel
    ):
        qs = MaterialMaster.objects.filter(
            material_code__in=Subquery(
                MaterialSaleMaster.objects.filter(
                    sales_organization_code=sale_org,
                    distribution_channel_code=distribution_channel,
                    status=STATUS_ACTIVE,
                )
                .distinct("material_code")
                .values("material_code")
            ),
        )
        return qs

    @classmethod
    def get_materials_by_code_distinct_material_code(cls, material_codes):
        return (
            MaterialMaster.objects.filter(material_code__in=material_codes)
            .distinct("material_code")
            .in_bulk(field_name="material_code")
        )

    @classmethod
    def get_product_hierarchy_by_material_code(cls, material_code):
        return (
            MaterialSaleMaster.objects.filter(material_code=material_code)
            .values_list("prodh", flat=True)
            .first()
        )

    @classmethod
    def get_material_by_description_en(cls, description):
        return MaterialMaster.objects.filter(description_en=description)
