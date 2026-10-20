from django.utils.cache import patch_cache_control


class PrivatePagesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/static/"):
            patch_cache_control(response, private=True, no_store=True, max_age=0)
        if not request.path.startswith("/admin/"):
            response["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; "
                "base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'"
            )
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
