import logging
from enum import Enum


class ProductGroup(Enum):
    PRODUCT_GROUP_1 = ["K01", "K09"]
    PRODUCT_GROUP_2 = ["K02", "K04", "K06", "K10", "K11", "K12"]
    PRODUCT_GROUP = PRODUCT_GROUP_1 + PRODUCT_GROUP_2

    @staticmethod
    def get_all_product_groups():
        return ProductGroup.PRODUCT_GROUP

    @staticmethod
    def get_product_group_2():
        return ProductGroup.PRODUCT_GROUP_2

    @staticmethod
    def get_product_group_1():
        return ProductGroup.PRODUCT_GROUP_1

    @staticmethod
    def is_default_plant_value(product_group):
        return product_group in ProductGroup.PRODUCT_GROUP_1.value

    @staticmethod
    def is_iplan_integration_required(order):
        logging.info(
            f"Product group for order id {order.id} and so_no {order.so_no}  is  {order.product_group} "
            f" and iplan interation is {order.product_group in ProductGroup.PRODUCT_GROUP_1.value}"
        )
        return order.product_group in ProductGroup.PRODUCT_GROUP_1.value


class ProductGroupDescription(Enum):
    K01 = "Kraft Roll"
    K02 = "Ream"
    K04 = "Bag"
    K06 = "Slit"
    K09 = "Gypsum"
    K10 = "Other Product"
    K11 = "Pro Block"
    K12 = "Plastic Pellet"


class SalesUnitEnum(Enum):
    SALES_QTY_IN_DECIMAL = ["RM", "TON"]

    @staticmethod
    def is_qty_conversion_to_decimal(sales_unit):
        return sales_unit in SalesUnitEnum.SALES_QTY_IN_DECIMAL.value


def get_enum_key(enum_class, enum_value):
    try:
        for key, value in enum_class.__members__.items():
            if value == enum_value:
                return key
    except Exception as e:
        logging.info(f"Enum value not found in the Enum {enum_class} if {e}")
