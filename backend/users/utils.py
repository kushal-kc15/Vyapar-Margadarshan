def get_client_ip(request):
    """
    Extract a single client IP string from the request.
    Supports Cloudflare (CF-Connecting-IP), X-Forwarded-For, and REMOTE_ADDR.
    """
    cf_ip = request.META.get("HTTP_CF_CONNECTING_IP")
    if cf_ip:
        return cf_ip.strip()

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    remote_addr = request.META.get("REMOTE_ADDR")
    return remote_addr.strip() if remote_addr else None
