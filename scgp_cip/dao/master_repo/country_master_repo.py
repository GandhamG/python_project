from sap_master_data.models import CountryMaster


class CountryMasterRepo:
    @classmethod
    def get_all_country_master_data(cls):
        return CountryMaster.objects.all()

    @classmethod
    def get_country_by_code(cls, code):
        if code:
            return CountryMaster.objects.filter(country_code=code).first()
