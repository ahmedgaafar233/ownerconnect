from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


def bearer_client(user):
    """
    A client that authenticates with a real JWT. force_authenticate() skips
    the authentication classes entirely, so it can't exercise anything that
    lives in TenantJWTAuthentication (e.g. which resort the request is
    scoped to).
    """
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client
