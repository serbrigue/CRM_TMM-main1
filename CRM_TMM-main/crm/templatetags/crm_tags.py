from django import template

# Crea una instancia de la librería de plantillas
register = template.Library()

@register.filter
def sub(value, arg):
    """
    Resta el argumento (arg) del valor (value).
    Uso: {{ valor|sub:argumento }}
    
    Ejemplo: {{ 10000|sub:3000 }} devolverá 7000.
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        # Devuelve el valor original si hay un error (ej. si no son números)
        return value