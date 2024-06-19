from sap_migration.models import SalesOfficeMaster


class SalesOfficeMasterRepo:
    @classmethod
    def get_sale_office_by_code(cls, sales_off_code):
        return SalesOfficeMaster.objects.filter(code=sales_off_code).first()
