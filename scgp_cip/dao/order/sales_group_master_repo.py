from sap_master_data.models import SalesGroup
from sap_migration.models import SalesGroupMaster


class SalesGroupMasterRepo:
    @classmethod
    def get_sales_group_by_code(cls, sales_group_code):
        return SalesGroupMaster.objects.filter(code=sales_group_code).first()

    @classmethod
    def get_sales_group_by_sales_group_code(cls, sales_group_code):
        return SalesGroup.objects.filter(sales_group_code=sales_group_code).first()
