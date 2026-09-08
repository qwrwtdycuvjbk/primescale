"""
Cookie and JWT helper utilities for Next.js BFF and browser authentication.
Implements HttpOnly, SameSite=Lax, Secure cookie management.
"""

from django.conf import settings
from rest_framework.response import Response


def set_auth_cookies(response: Response, access_token: str, refresh_token: str = None) -> Response:
    """
    Sets secure HttpOnly cookies on the HTTP response for Next.js App Router / middleware.
    """
    secure = not settings.DEBUG
    # Access token cookie: lifetime matching JWT (60m)
    access_lifetime = getattr(settings, "JWT_ACCESS_MINUTES", 60) * 60

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=access_lifetime,
        httponly=True,
        secure=secure,
        samesite="Lax",
        path="/",
    )

    if refresh_token:
        refresh_lifetime = getattr(settings, "JWT_REFRESH_DAYS", 7) * 86400
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=refresh_lifetime,
            httponly=True,
            secure=secure,
            samesite="Lax",
            path="/api/v1/auth/",
        )

    return response


def clear_auth_cookies(response: Response) -> Response:
    """
    Clears the authentication cookies upon logout.
    """
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/v1/auth/")
    return response
