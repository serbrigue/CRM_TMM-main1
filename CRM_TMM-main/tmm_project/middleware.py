from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTAuthMiddleware:
    """Middleware that attempts to authenticate the request using a Bearer JWT.

    If a valid token is present in the Authorization header (Bearer ...), the
    middleware sets request.user to the authenticated user. If authentication
    fails or no token is present, it leaves request.user untouched.
    This allows existing Django views decorated with @login_required or
    @user_passes_test to work with JWT tokens.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def __call__(self, request):
        # If no Authorization header is present, try reading the access token from cookie
        if 'HTTP_AUTHORIZATION' not in request.META:
            access_token = request.COOKIES.get('access_token')
            if access_token:
                # Set the Authorization header so SimpleJWT can pick it up
                request.META['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
        try:
            auth_result = self.jwt_auth.authenticate(request)
            if auth_result is not None:
                user, token = auth_result
                # Override request.user only when a JWT authenticated user is found
                request.user = user
        except Exception:
            # Any failure to authenticate via JWT should not raise; fall back
            # to the default authentication mechanisms (session middleware).
            pass

        return self.get_response(request)
