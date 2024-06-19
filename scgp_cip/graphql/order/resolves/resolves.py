from scgp_cip.dao.master_repo.country_master_repo import CountryMasterRepo
from scgp_cip.dao.master_repo.transport_zone_repo import TransportZoneRepo


def resolve_transportation(countrycode):
    return TransportZoneRepo.get_transport_zone_by_country_code(countrycode)


def resolve_country_master():
    return CountryMasterRepo.get_all_country_master_data()
