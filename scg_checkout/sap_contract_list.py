from datetime import datetime, timedelta

from sap_migration.models import (
    CompanyMaster,
    Contract,
    SalesOrganizationMaster,
    SoldToMaster,
)


def sap_contract_mapping(rs, customer_no=""):
    if not rs:
        return

    list_contract_create = []
    list_contract_update = []

    contracts_from_sap = {contract["contractNo"]: contract for contract in rs}
    mapped_contracts = {
        item.code: item
        for item in Contract.objects.filter(code__in=contracts_from_sap).all()
    }
    mapped_sale_orgs = {
        item.code: item for item in SalesOrganizationMaster.objects.all()
    }
    mapped_companies = {item.code: item for item in CompanyMaster.objects.all()}

    mock_start_date = datetime.strftime(datetime.now().date(), "%d/%m/%Y")
    mock_end_date = datetime.strftime(
        datetime.now().date() + timedelta(days=30), "%d/%m/%Y"
    )

    sold_to_code = rs[0].get("customerId")
    sold_to = SoldToMaster.objects.filter(sold_to_code=sold_to_code).first()
    if customer_no and "-" in customer_no:
        _, customer_name = customer_no.split(" - ")
        sold_to = SoldToMaster.objects.filter(
            sold_to_code=sold_to_code, sold_to_name=customer_name
        ).first()

    for item in contracts_from_sap.values():
        contract_code = item.get("contractNo")
        if contract_code is None:
            continue

        sale_org_code = item.get("saleOrg", "0750")
        sale_org = mapped_sale_orgs.get(sale_org_code, None)
        business_unit = sale_org.business_unit if sale_org else None

        mapping = {
            "sold_to": sold_to,
            "code": item.get("contractNo", ""),
            "company": mapped_companies.get(str(item.get("company", "0750")), None),
            "sales_organization": sale_org,
            "business_unit": business_unit,
            "start_date": datetime.strptime(
                item.get("startDate", mock_start_date), "%d/%m/%Y"
            ).date(),
            "end_date": datetime.strptime(
                item.get("endDate", mock_end_date), "%d/%m/%Y"
            ).date(),
            "payment_term": item.get("paymentConditionName", ""),
            "po_no": item.get("poNo", ""),
            "incoterm": item.get("incoterm"),
            "ship_to": f'{item.get("shipToCode", "")} - {item.get("shipToName", "")}',
            "ship_to_name": item.get("shipToName", ""),
            "ship_to_country": item.get("country", ""),
            "project_name": item.get("projectName", ""),
            "po_date": datetime.now().date(),
            "sold_to_code": item.get("customerId", ""),
            "contract_status": item.get("contractStatus", ""),
            "prc_group1": item.get("prcGroup1", ""),
            "payment_term_key": item.get("paymentCondition", ""),
        }

        contract = mapped_contracts.get(contract_code)
        if contract is None:
            new_contract = Contract(**mapping)
            list_contract_create.append(new_contract)
        else:
            for k, v in mapping.items():
                setattr(contract, k, v)
            list_contract_update.append(contract)

    if len(list_contract_create) > 0:
        Contract.objects.bulk_create(list_contract_create)

    if len(list_contract_update) > 0:
        Contract.objects.bulk_update(list_contract_update, list(mapping.keys()))
