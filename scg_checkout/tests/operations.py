BUSINESS_UNITS_QUERY = """
query businessUnits($first: Int!) {
  businessUnits(first: $first) {
    edges {
      node {
        id
        name
        companies {
          id
          name
        }
      }
    }
  }
}
"""

CONTRACTS_QUERY = """
query QueryContracts(
            $customerId: ID!,
            $first: Int!,
            $contractIds: [ID!],
            $filter: TempContractFilterInput,
            $productSort: ProductSortingInput,
        ) {
            contracts(customerId:$customerId, first:$first, filter:$filter, contractIds: $contractIds) {
                edges {
                    node {
                        id
                        customer {
                            id
                            lastName
                            firstName
                        }
                        company{
                            id
                            name
                            businessUnit {
                                name
                            }
                        }
                        projectName
                        startDate
                        endDate
                        paymentTerm
                        products (sortBy: $productSort) {
                            id
                            name
                            remain
                        }
                    }
                }
            }
        }
"""

CONTRACT_QUERY = """
query QueryContract(
            $contractId: ID!,
            $productSort: ProductSortingInput,
        ) {
            contract(contractId: $contractId)  {
                id
                customer {
                    id
                    lastName
                    firstName
                }
                company {
                    id
                    name
                    businessUnit{
                        id
                        name
                    }
                }
                projectName
                startDate
                endDate
                paymentTerm
                products (sortBy: $productSort) {
                    id
                    price
                    name
                    total
                    remain
                    salesUnit
                }
            }
        }
"""

CONTRACT_ORDER_CREATE_MUTATION = """
mutation createContractOrder($orderInformation: OrderInformationInput, $lines: [ContractOrderLineInput!]!){
    createContractOrder(
        input: {
          orderInformation: $orderInformation
          lines: $lines
        }
    ) {
        order {
            id
            customer{
                id
            }
            orderLines{
                id
                variant{
                  id
                }
                quantity
            }
            status
        }
    }
}
"""

CONTRACT_UPDATE_ORDER_MUTATION = """
mutation updateContractOrder($id : ID!, $input: ContractOrderUpdateInput!){
    updateContractOrder(id: $id, input: $input){
        order {
            id
            customer{
                id
            }
            orderLines{
                id
                checkoutLine{
                    id
                }
            }
        }
    }
}
"""

CONTRACT_DELETE_ORDER_MUTATION = """
mutation deleteContractOrder ($id: ID!){
    deleteContractOrder(id: $id){
        order{
            id
        }
    }
}
"""

CONTRACT_DELETE_ORDER_LINES_MUTATION = """
mutation deleteContractOrderLines($ids: [ID]!){
    deleteContractOrderLines(ids: $ids){
        orderLines{
            id
        }
    }
}
"""

CONTRACT_DELETE_ORDER_LINE_MUTATION = """
mutation deleteContractOrderLine($id: ID!){
    deleteContractOrderLine(id: $id){
        orderLine{
            id
        }
    }
}
"""

CREATE_CONTRACT_CHECKOUT = """
mutation createContractCheckout($input: ContractCheckoutCreateInput!){
    createContractCheckout(input: $input) {
        errors{
            message
        }
        checkout {
            id
            lines {
                id
                quantity
                contractProduct{
                    id
                    name
                }
                variant{
                    id
                    name
                }
                product{
                    id
                    name
                }
            }
        }
    }
}
"""

UPDATE_CONTRACT_CHECKOUT = """
mutation createContractCheckout($id:ID! $input: ContractCheckoutUpdateInput!){
    updateContractCheckout(id:$id input:$input) {
        errors{
            message
        }
        checkout {
            id
            quantity
            contract{
                id
                projectName
            }
            lines {
                id
                product{
                    id
                    name
                }
                quantity
            }
        }
    }
}
"""

DELETE_CONTRACT_CHECKOUT_LINES = """
mutation deleteContractCheckoutLines($checkoutLineIds: [ID]!){
    deleteContractCheckoutLines(checkoutLineIds: $checkoutLineIds){
        status
        errors {
            message
        }
    }
}
"""

EXPORT_ALTERNATIVE_MATERIAL = """
mutation exportAlternativeMaterial{
    exportAlternativeMaterial {
        errors {
            code
            message
        }
        fileName
        contentType
        exportedFileBase64
    }
}
"""
EXPORT_LOG_CHANGE = """
mutation exportLogChange{
   exportLogChange{
        errors {
            code
            message
        }
        fileName
        contentType
        exportedFileBase64
    }
}
"""
