from django.contrib.auth import logout


class InactiveUserLogoutMiddleware:
    """Immediately invalidate an authenticated session if the account was deactivated."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not user.is_active:
            logout(request)
        return self.get_response(request)
