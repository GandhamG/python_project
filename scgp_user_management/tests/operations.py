SCGP_USER_SALES_REGISTER_MUTATION = """
mutation scgpUserRegister($input: ScgpUserRegisterInput!) {
  scgpUserRegister(input: $input ) {
    user {
      id
      email
      firstName
      lastName
      permissionGroups {
        id
        name
      }
      extendData {
        adUser
        saleId
        employeeId
        userParentGroup {
          id
          name
        }
        createdBy {
          email
        }
        updatedBy {
          email
        }
      }
      dateJoined
      updatedAt
      lastLogin
      isActive
    }
    errors {
      message
    }
  }
}
"""

SCGP_USER_OTHER_REGISTER_MUTATION = """
mutation scgpUserRegister($input: ScgpUserRegisterInput!) {
  scgpUserRegister(input: $input ) {
    user {
      id
      email
      firstName
      lastName
      permissionGroups {
        id
        name
      }
      extendData {
        adUser
        employeeId
        scgpBus {
          id
          name
        }
        scgpSalesOrganizations {
          id
          name
        }
        scgpSalesGroups {
          id
          name
        }
        scgpDistributionChannels {
          id
          name
        }
        scgpDivisions {
          id
          name
        }
        scgpSalesOffices {
          id
          name
        }
        userParentGroup {
          id
          name
        }
        createdBy {
          email
        }
        updatedBy {
          email
        }
      }
      dateJoined
      updatedAt
      lastLogin
      isActive
    }
    errors {
      message
    }
  }
}
"""

SCGP_USER_CUSTOMER_REGISTER_MUTATION = """
mutation scgpUserRegister($input: ScgpUserRegisterInput!) {
  scgpUserRegister(input: $input) {
    user {
      id
      email
      firstName
      lastName
      permissionGroups {
        id
        name
      }
      soldTos {
        code
        name
      }
      extendData {
        customerType
        companyEmail
        displayName
        userParentGroup {
          id
          name
        }
        createdBy {
          email
        }
        updatedBy {
          email
        }
      }
      dateJoined
      updatedAt
      lastLogin
      isActive
    }
    errors {
      message
    }
  }
}
"""

SCGP_USER_UPDATE_MUTATION = """
mutation scgpUserUpdate($id: ID!, $input: ScgpUserUpdateInput!) {
  scgpUserUpdate(id: $id, input: $input) {
    user {
      id
      email
      firstName
      lastName
      permissionGroups {
        id
        name
      }
      soldTos {
        code
        name
      }
      extendData {
        customerType
        companyEmail
        displayName
        userParentGroup {
          id
          name
        }
        createdBy {
          email
        }
        updatedBy {
          email
        }
      }
      dateJoined
      updatedAt
      lastLogin
      isActive
    }
    errors {
      message
    }
  }
}
"""

SCGP_USER_SEND_MAIL_RESET_PASSWORD = """
mutation scgpUserSendMailResetPassword($email: String!) {
  scgpUserSendMailResetPassword(email: $email) {
    message
    errors {
      field
      message
      code
    }
  }
}
"""

SCGP_USER_CONFIRM_RESET_PASSWORD = """
mutation scgpUserConfirmResetPassword(
  $email: String!
  $token: String!
  $new_password: String!
  $confirm_password: String!
) {
  scgpUserConfirmResetPassword(
    email: $email
    token: $token
    newPassword: $new_password
    confirmPassword: $confirm_password
  ) {
    message
    errors {
      field
      message
      code
    }
  }
}
"""
