from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Permite acceder a un dict por clave dinámica en templates: {{ dict|get_item:key }}"""
    if isinstance(dictionary, dict):
        val = dictionary.get(key, "-")
        return val if val is not None else "-"
    return "-"
