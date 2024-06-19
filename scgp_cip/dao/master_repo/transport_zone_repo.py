from sap_master_data.models import TransportZone


class TransportZoneRepo:
    @classmethod
    def get_transport_zone_by_country_code(cls, countrycode):
        return TransportZone.objects.filter(country_code=countrycode).all()
