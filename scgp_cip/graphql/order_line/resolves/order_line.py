from scgp_cip.dao.order_line.material_purchase_master_repo import MaterialPurchaseMasterRepo
from scgp_cip.graphql.order_line.types import PlantResponse
from scgp_cip.common.enum import SearchMaterialBy
from scgp_cip.dao.order_line.material_master_repo import MaterialMasterRepo
from scgp_cip.dao.order_line.sold_to_material_master_repo import SoldToMaterialMasterRepo


def resolve_get_plants_by_mat_code(info, kwargs):
    material_code = kwargs.get("material_code", None)
    plants_qs = MaterialPurchaseMasterRepo.get_mat_pur_master_by_material_code(material_code)
    return [PlantResponse(plant_code=plant.get('plant_code', ""), plant_name=plant.get('plant_name', ""))
            for plant in plants_qs.values("plant_code", "plant_name")]


def resolve_search_suggestion_material(info, kwargs):
    sale_org = kwargs.get("sale_org", None)
    distribution_channel = kwargs.get("distribution_channel", None)
    search_by = kwargs.get("search_by", None)
    if SearchMaterialBy.MAT_CODE == search_by:
        return MaterialMasterRepo.get_material_master_by_sale_org_dist_channel(sale_org, distribution_channel)
    elif SearchMaterialBy.CUST_MAT_CODE == search_by:
        sold_to = kwargs.get("sold_to", None)
        return SoldToMaterialMasterRepo.get_sold_to_material_master_by_sale_org_dist_channel_sold_to(
            sale_org, distribution_channel, sold_to)
    else:
        return []
