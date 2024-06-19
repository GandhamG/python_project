CUSTOMER_QUERY = """
query QueryCustomer(
    $id: ID!
){
    customer(id:$id)
{
    id
    email
    lastName
    firstName
    addresses{
      streetAddress1
      streetAddress2
    }
}
}
"""
