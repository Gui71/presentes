def client_ip(request):
    return request.META.get("REMOTE_ADDR")
