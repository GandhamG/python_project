from sap_migration import models as sap_migration_models
from scg_checkout.graphql.enums import LanguageCode

# from scg_checkout.graphql.implementations.sap import get_languages_from_contract_details

# This class is being done to avoid circular reference causing beween helper.py and sap.py
def get_order_text_language(contract_details, order, text_id, is_header=False):
    # This method is duplicate code of get_order_text_language of sap.py
    # need to do duplication to avoid circular reference
    contract = order.contract.code
    languages = get_languages_from_contract_details(
        contract_details, contract, text_id, is_header
    )
    if languages:
        if LanguageCode.EN.value in languages:
            return LanguageCode.EN.value
        elif languages:
            return languages.pop()
        else:
            return None


def get_languages_from_contract_details(contract_details, contract, text_id, is_header):
    languages = set()
    if not contract or not contract_details:
        return None
    if contract_details:
        for contract_detail in contract_details:
            if contract_detail.get("contractNo") == contract:
                order_texts = contract_detail.get("orderText")
                for order_text in order_texts:
                    if is_header and order_text.get("itemNo") == "000000":
                        if text_id == order_text.get("textId"):
                            languages.add(order_text.get("lang"))
                    elif not is_header and order_text.get("itemNo") != "000000":
                        if text_id == order_text.get("textId"):
                            languages.add(order_text.get("lang"))
    return languages


def add_lang_to_sap_text_field(order, order_text, text_id, item_no):
    lang = get_lang_by_order_text_lang_db(order.contract, text_id, item_no)
    if lang:
        order_text["language"] = lang


def get_lang_by_order_text_lang_db(contract, text_id, item_no):
    item_no = item_no.rjust(6, "0") if item_no else None
    order_text_lang = sap_migration_models.OrderTextLang.objects.filter(
        contract=contract, text_id=text_id, item_no=item_no
    ).first()
    return order_text_lang.language if order_text_lang else None
