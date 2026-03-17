# utilisateur/middleware.py
from channels.middleware import BaseMiddleware
from urllib.parse import parse_qs


async def get_user_from_token(token_key):
    from channels.db import database_sync_to_async
    from django.contrib.auth.models import AnonymousUser
    from rest_framework.authtoken.models import Token

    @database_sync_to_async
    def fetch_user():
        try:
            token = Token.objects.select_related('user').get(key=token_key)
            return token.user
        except Exception:
            return AnonymousUser()

    return await fetch_user()


class TokenAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser

        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_key = params.get("token", [None])[0]

        if token_key:
            scope["user"] = await get_user_from_token(token_key)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)