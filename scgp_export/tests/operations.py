QUERY_EXPORT_PI = """
query exportPi ($id: ID!){
    exportPi (id: $id)
    {
        id
        code
        poNo
        soldToName
        shipToName
        shipToCountry
        incoterm
        paymentTerm
        piProducts{
            product{
                id
                name
            }
            totalQuantity
            remainingQuantity
            pricePerUnit
            quantityUnit
            currency
            weightUnit
        }
    }
}
"""

CREATE_EXPORT_CART_MUTATIONS = """
mutation createExportCart($input: ExportCartCreateInput!){
    createExportCart(input: $input){
        cart{
            id
            items{
                id
            }
        }
        errors{
            message
        }
    }
}
"""

EXPORT_PIS_QUERY = """
query exportPis($first: Int, $searchCode: String, $searchSoldTo: String) {
  exportPis(
    first: $first
    filter: { code: $searchCode, soldTo: $searchSoldTo }
  ) {
    edges {
      node {
        id
        code
        poNo
        soldTo {
          id
          displayText
        }
        shipToName
        shipToCountry
        incoterm
        paymentTerm
      }
    }
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }
  }
}
"""

EXPORT_SOLD_TOS_QUERY = """
query exportSoldTos($first: Int, $search: String) {
  exportSoldTos(first: $first, filter: { search: $search }) {
    totalCount
    edges {
      node {
        id
        name
        code
        displayText
      }
    }
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }
  }
}
"""

EXPORT_CARTS_QUERY = """
query exportCarts ($first:Int)
{
  exportCarts{
    totalPi
    totalSoldTo
    totalCartItem
    carts(first: $first){
      pageInfo{
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
      edges{
        node{
          id
          pi{
            code
          }
          soldTo{
            name
          }
          totalItems
        }
      }
      totalCount
    }
  }
}
"""

EXPORT_CART_ITEMS_QUERY = """
query exportCart ($id:ID!, $first:Int)
{
  exportCart(id: $id) {
    pi {
      id
      code
    }
    soldTo {
      id
      code
      name
    }
    items(first: $first) {
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
      edges {
        node {
          id
          piProduct {
            totalQuantity
            remainingQuantity
            pricePerUnit
            weightUnit
          }
          quantity
        }
      }
    }
  }
}
"""

DELETE_EXPORT_CART_ITEMS = """
mutation deleteExportCartItems($cartItemIds:[ID]!)
{
  deleteExportCartItems(cartItemIds:$cartItemIds){
    status
    cart{
        quantity
    }
    errors{
        message
    }
  }
}
"""

UPDATE_EXPORT_CART_MUTATION = """
mutation UpdateExportCart($id: ID!, $input: ExportCartUpdateInput!){
  updateExportCart(id:$id, input:$input){
    cart{
      id
      pi{
        id
        code
        poNo
      }
      soldTo{
        id
      }
      createdBy{
        id
      }
      items{
        id
        quantity
        piProduct{
          id
        }
      }
    }
  }
}
"""

DELETE_EXPORT_ORDER_LINES_MUTATION = """
mutation DeleteExportOrderLines($deleteAll: Boolean, $ids:[ID], $orderId: ID){
  deleteExportOrderLines(deleteAll: $deleteAll, ids: $ids, orderId: $orderId){
    errors{
      field
      message
      code
    }
    status
  }
}
"""

ADD_PRODUCT_TO_EXPORT_ORDER_MUTATION = """
mutation AddProductsToExportOrder($id: ID!, $input: [ExportOrderLineAddProductInput!]!){
  addProductsToExportOrder(id: $id, input: $input){
    errors{
      field
      message
      code
    }
    order{
      id
    }
  }
}
"""

CREATE_EXPORT_ORDER = """
mutation CreateExportOrder($input: ExportOrderCreateInput!) {
  createExportOrder(input: $input) {
    order {
      id
      pi {
        id
        code
      }
      netPrice
      totalPrice
      taxAmount
      status
      lines (first: 10, sortBy: {
        direction: ASC,
        field: MATERIAL_CODE
      }) {
        edges {
          node {
            id
            netPrice
            materialCode
            quantity
            commissionAmount
          }
        }
        totalCount
        latestPageItemNumber
      }
    }
    errors {
      field
      message
      code
    }
  }
}
"""

UPDATE_EXPORT_ORDER_MUTATION = """
mutation UpdateExportOrder(
  $id: ID!,
  $input: ExportOrderUpdateInput!
) {
  updateExportOrder(
    id: $id,
    input: $input
  ) {
    errors {
      field
      message
      code
    }
    order {
      id
      status
      poDate
      poNo
      requestDate
      refPiNo
      usage
      unloadingPoint
      portOfDischarge
      portOfLoading
      noOfContainers
      uom
      gwUom
      etd
      eta
      dlcExpiryDate
      dlcNo
      dlcLatestDeliveryDate
      description
      payer
      endCustomer
      paymentInstruction
      remark
      productionInformation
      internalCommentToWarehouse
      placeOfDelivery
      orderType
      salesOrganization {
        id
      }
      distributionChannel {
        id
      }
      division {
        id
      }
      salesOffice {
        id
      }
      salesGroup {
        id
      }
      updatedAt
    }
  }
}
"""

UPDATE_EXPORT_ORDER_LINES_MUTATION = """
mutation UpdateExportOrderLines($id: ID!, $input: [ExportOrderLineUpdateInput!]!) {
  updateExportOrderLines(input: $input, orderId: $id) {
    order {
      id
      totalPrice
      taxAmount
      currency
      status
      requestDeliveryDate
      orderType
      shippingMark
      contactPerson
    }
    errors {
      field
      message
      code
    }
  }
}
"""

UPDATE_ALL_EXPORT_ORDER_LINES_MUTATION = """
mutation UpdateAllExportOrderLine(
  $id: ID!,
  $input: ExportOrderLineUpdateAllInput!
) {
  updateAllExportOrderLine(
    id: $id,
    input: $input
  ) {
    errors {
      field
      message
      code
    }
    order {
      id
      totalPrice
    }
  }
}
"""

QUERY_EXPORT_ORDERS = """
query exportOrders(
  $sortBy: ExportOrderSortingInput
  $filter: ExportOrderFilterInput
  $first: Int
  $before: String
  $after: String
) {
  exportOrders(
    sortBy: $sortBy
    filter: $filter
    first: $first
    before: $before
    after: $after
  ) {
    pageInfo {
      hasNextPage
      hasPreviousPage
    }
    edges {
      node {
        id
        pi {
          code
          shipToName
          shipToCountry
          soldTo {
            name
          }
        }
        eoNo
        poNo
        incoterm
        paymentTerm
        status
        statusSap
        createdAt
        salesOrganization {
          name
          businessUnit {
            name
          }
        }
      }
    }
    totalCount
    latestPageItemNumber
  }
}
"""

FILTER_BUSINESS_EXPORT_ORDER = """
query filterBusinessExportOrder{
  filterBusinessExportOrder{
    name
    id
  }
}
"""

FILTER_COMPANIES_EXPORT_ORDER_BY_BUSINESS_UNIT = """
query filterCompaniesExportOrderByBusinessUnit($first:Int, $filter:ExportCompaniesFilterInput){
  filterCompaniesExportOrderByBusinessUnit(first:$first, filter:$filter){
    edges{
      node{
        name
        code
      }
    }
  }
}
"""

FILTER_COMPANIES_EXPORT_ORDER_BY_USER_LOGIN = """
query filterCompaniesExportOrderByUserLogin{
  filterCompaniesExportOrderByUserLogin{
    name
    code
  }
}
"""


FILTER_SOLD_TO_EXPORT_ORDER = """
query filterSoldToExportOrder($filter:ExportSoldToFilterInput, $first:Int)
{
  filterSoldToExportOrder(filter:$filter, first:$first){
    edges{
      node{
        addressText
        code
        name
      }
    }
  }
}
"""
