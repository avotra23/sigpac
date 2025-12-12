from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def delete_session_key(context, key):
    """
    Supprime la clé spécifiée de la session après l'affichage du template.
    """
    if key in context['request'].session:
        del context['request'].session[key]
    return ''