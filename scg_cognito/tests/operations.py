GENERATE_TOKEN_MUTATION = """
mutation generateToken(
    $idToken: String!
) {
    generateToken(idToken: $idToken) {
        token
        refreshToken
        csrfToken
        user {
            id,
            email
        }
        errors {
            message,
            code
        }
    }
}
"""
