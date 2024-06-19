CUSTOMER_CONTRACT_QUERY = """
query customerContractDetail(
    $id:ID!,
    $productSort: CustomerProductSortingInput,
    ){
          customerContractDetail(id: $id) {
                code
                customer{
                  id,
                  customerNo
                }
                projectName
                startDate
                endDate
                paymentTerm
                company {
                      businessUnit {
                            name
                      }
                      name
                }
                products (sortBy: $productSort){
                      weight
                      remainingQuantity
                      totalQuantity
                      pricePerUnit
                      product {
                            name
                      }
                }
          }
    }
"""

CUSTOMER_CONTRACT_NO_SORT_QUERY = """
query customerContractDetail(
    $id:ID!
    ){
          customerContractDetail(id: $id) {
                code
                customer{
                  id,
                  customerNo
                }
                projectName
                startDate
                endDate
                paymentTerm
                company {
                      businessUnit {
                            name
                      }
                      name
                }
                products {
                      weight
                      remainingQuantity
                      totalQuantity
                      pricePerUnit
                      product {
                            name
                      }
                }
          }
    }
"""

CREATE_DRAFT_ORDER_MUTATION = """
mutation CreateCustomerOrder($input: CreateCustomerOrderInput!) {
  createCustomerOrder(input: $input) {
    order {
      id
      contract {
        id
        soldTo {
          id
          code
          name
          representatives {
            id
            email
          }
        }
        company {
          id
          name
        }
        code
        projectName
        startDate
        endDate
        paymentTerm
      }
      totalPrice
      totalPriceIncTax
      taxAmount
      status
      orderDate
      orderNo
      requestDeliveryDate
      shipTo
      billTo
      unloadingPoint
      remarkForInvoice
      createdAt
      updatedAt
      lines {
        order {
          orderNo
        }
        contractProduct {
          id
          contract {
            id
            projectName
          }
          product {
            id
            name
            slug
          }
          pricePerUnit
          quantityUnit
          currency
          weight
          weightUnit
        }
        variant {
          id
          name
          slug
          product {
            id
          }
        }
        quantity
        quantityUnit
        weightPerUnit
        totalWeight
        pricePerUnit
        totalPrice
        requestDeliveryDate
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


CREATE_CUSTOMER_CART = """
mutation createCustomerCart ($input: CustomerCartCreateInput!){
    createCustomerCart(input: $input){
        errors{
            message
        }
        cart {
            id
            cartItems{
                id
            }
        }
    }
}
"""


CUSTOMER_CONTRACT_PRODUCT_QUERY = """
query customerContractProduct(
        $contractId: ID!,
        $productId: ID!
    ){
        customerContractProduct(contractId: $contractId, productId: $productId)
        {
            product{
                name
            }
            totalQuantity
            remainingQuantity
            pricePerUnit
            currency
            weightUnit
        }
    }
"""


CUSTOMER_CARTS_QUERY = """
query customerCarts ($first: Int){
  customerCarts(first: $first, sortBy: {direction: DESC field: LINES_COUNT}) {
    edges {
      node {
        id
        contract {
          code
          projectName
        }
        quantity
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


CUSTOMER_CART_QUERY = """
query customerCart($cartId: ID!){
  customerCart(id: $cartId) {
    id
    contract {
      code
      projectName
    }
    quantity
    cartItems {
      quantity
      variant {
        id
        name
      }
      contractProduct {
        quantityUnit
        product {
          name
          variants {
            id
            name
          }
        }
      }
    }
  }
}
"""


CUSTOMER_CART_TOTALS_QUERY = """
query {
  customerCartTotals {
    totalContracts
    totalProducts
  }
}
"""


DELETE_CUSTOMER_CART_ITEMS_MUTATION = """
mutation deleteCustomerCartItems($cartItemIds: [ID]!) {
  deleteCustomerCartItems(cartItemIds: $cartItemIds) {
    status
    errors {
      message
    }
  }
}
"""

CUSTOMER_ORDER_QUERY = """
query CustomerOrder(
  $orderId: ID!
  $before: String
  $after: String
  $first: Int
  $last: Int
) {
  customerOrder(orderId: $orderId) {
    id
    createdBy{
      addresses{
        streetAddress1
        streetAddress2
      }
    }
    contract {
      id
      soldTo{
        name
      }
      customer{
        firstName
        lastName
      }
      code
      projectName
      paymentTerm
    }
    totalPrice
    totalPriceIncTax
    taxAmount
    orderDate
    orderNo
    requestDeliveryDate
    shipTo
    billTo
    unloadingPoint
    remarkForInvoice
    lines(before: $before, after: $after, first: $first, last: $last) {
      totalCount
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
      edges {
        node {
          id
          quantity
          quantityUnit
          weightPerUnit
          totalWeight
          pricePerUnit
          totalPrice
          contractProduct {
            contract {
              paymentTerm
            }
            totalQuantity
            remainingQuantity
          }
          variant {
            name
          }
          requestDeliveryDate
        }
      }
    }
  }
}

"""


UPDATE_CUSTOMER_ORDER_MUTATION = """
mutation UpdateCustomerOrder($id: ID!, $input: CustomerOrderInformationUpdateInput!) {
  updateCustomerOrder(id: $id, input: $input) {
    errors {
      field
      message
      code
    }
    order {
      id
    }
  }
}
"""


UPDATE_CUSTOMER_ORDER_LINES_MUTATION = """
mutation UpdateCustomerOrderLines($orderId: ID!, $input: CustomerOrderLinesUpdateInput!) {
  updateCustomerOrderLines(orderId: $orderId, input: $input) {
    errors {
      field
      message
      code
    }
    order {
      id
    }
  }
}
"""

DELETE_CUSTOMER_ORDER_LINES = """
mutation DeleteCustomerOrderLines($ids: [ID], $deleteAll: Boolean, $orderId: ID) {
  deleteCustomerOrderLines(ids: $ids, deleteAll: $deleteAll, orderId: $orderId) {
    errors {
      field
      message
    }
    status
  }
}

"""


ADD_PRODUCTS_TO_CUSTOMER_ORDER = """
mutation AddProductToCustomerOrder($id: ID!, $input: [CustomerOrderLineInput!]!) {
  addProductToCustomerOrder(id: $id, input: $input) {
    order {
      id
    }
    errors {
      message
      code
    }
  }
}
"""

UPDATE_CUSTOMER_CART_MUTATIONS = """
mutation UpdateCustomerCart($id: ID!, $input: CustomerCartUpdateInput!){
  updateCustomerCart(id:$id,
    input:$input){
    errors{
      message
    }
    cart{
      id
      contract{
        code
      }
      createdBy{
        id
      }
      quantity
      cartItems{
        id
        variant{
          name
        }
        quantity
      }
    }
  }
}
"""
