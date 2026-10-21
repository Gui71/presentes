from ipaddress import ip_address
from django.conf import settings

def client_ip(request):
    try:
        peer = str(ip_address(request.META.get("REMOTE_ADDR", "")))
    except ValueError:
        return None

    if peer in getattr(settings, "TRUSTED_PROXY_IPS", []):
        forwarded = request.META.get("HTTP_X_REAL_IP", "").strip()
        try:
            return str(ip_address(forwarded))
        except ValueError:
            pass

    return peer
