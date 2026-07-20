from django.http import JsonResponse
from django.db import connection


def root(request):
    return JsonResponse({
        "message": "Vyapar Margadarshan API",
        "status": "ok"
    })


def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({
            "status": "ok",
            "database": "ok"
        })
    except Exception:
        return JsonResponse({
            "status": "error",
            "database": "error"
        }, status=503)