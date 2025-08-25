from django.http import JsonResponse

class AccessPolicyMiddleware:
    """
    Middleware to enforce role-based access policies.
    Attach this in settings.py MIDDLEWARE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip for unauthenticated requests
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Example: attach a helper method
        request.has_permission = lambda action: request.user.has_permission(action)
        return self.get_response(request)
