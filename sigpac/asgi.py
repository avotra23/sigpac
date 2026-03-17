import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sigpac.settings')
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from utilisateur.middleware import TokenAuthMiddleware
import pac.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": TokenAuthMiddleware(  # ← plus d'AllowedHostsOriginValidator
        URLRouter(
            pac.routing.websocket_urlpatterns
        )
    ),
})