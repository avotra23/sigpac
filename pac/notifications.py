from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

def notify_plainte(action: str, plainte, user_id: int):
    """
    Envoie une notification WebSocket lors d'un changement sur une plainte.
    
    :param action: 'created' | 'updated' | 'deleted'
    :param plainte: instance Plainte (ou dict avec id, n_chrono_tkk, statut)
    :param user_id: ID de l'utilisateur propriétaire de la plainte
    """
    channel_layer = get_channel_layer()

    # Construire le payload
    payload = {
        "type": "plainte_notification",    # mappe vers la méthode du consumer
        "data": {
            "event": action,               # 'created', 'updated', 'deleted'
            "plainte_id": plainte.id if hasattr(plainte, 'id') else plainte.get('id'),
            "n_chrono": plainte.n_chrono_tkk if hasattr(plainte, 'n_chrono_tkk') else plainte.get('n_chrono_tkk'),
            "statut": plainte.statut if hasattr(plainte, 'statut') else plainte.get('statut'),
            "user_id": user_id,
        }
    }

    # 1. Notifier le canal GLOBAL (admins, DCN)
    async_to_sync(channel_layer.group_send)(
        "plaintes_global",
        payload
    )

    # 2. Notifier le canal PERSONNEL de l'utilisateur créateur
    async_to_sync(channel_layer.group_send)(
        f"plaintes_user_{user_id}",
        payload
    )