from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Canal global pour les admins/DCN (toutes les plaintes)
    re_path(r'ws/plaintes/$', consumers.PlainteConsumer.as_asgi()),
    
    # Canal par utilisateur (plaintes personnelles)
    re_path(r'ws/plaintes/user/(?P<user_id>\d+)/$', consumers.PlainteUserConsumer.as_asgi()),
]