from django.db import transaction, IntegrityError
from django.db.models import F
from django.shortcuts import get_object_or_404
from ..models import Cliente, Inscripcion, Taller


def enroll_cliente_en_taller(taller_id, nombre, email, telefono=None, usuario=None):
    """Crear una inscripción para un cliente (posible invitado) en un taller.

    Args:
        taller_id (int): id del Taller.
        nombre (str): nombre del cliente.
        email (str): email del cliente.
        usuario (django.contrib.auth.models.User|None): usuario autenticado opcional.

    Returns:
        tuple: (inscripcion, created_flag, message)
          - inscripcion: instancia de Inscripcion o None en caso de error
          - created_flag: True si se creó, False si ya existía
          - message: string explicativo
    """
    taller = get_object_or_404(Taller, pk=taller_id)

    # Validación temprana de cupos
    if taller.cupos_disponibles <= 0:
        return (None, False, 'No hay cupos disponibles')

    # Determinar email/nombre desde usuario si existe
    if usuario and getattr(usuario, 'is_authenticated', False):
        cliente_email = usuario.email or email
        cliente_nombre = f"{usuario.first_name} {usuario.last_name}".strip() or nombre
        cliente_telefono = getattr(usuario, 'telefono', None) or telefono
    else:
        cliente_email = email
        cliente_nombre = nombre
        cliente_telefono = telefono

    try:
        with transaction.atomic():
            # 1. Bloquear la fila del taller para evitar condiciones de carrera (overselling)
            taller_locked = Taller.objects.select_for_update().get(pk=taller_id)

            # 2. Verificar cupos con el bloqueo activo
            if taller_locked.cupos_disponibles <= 0:
                return (None, False, 'No hay cupos disponibles')

            # 3. Obtener o crear cliente
            cliente, created_cliente = Cliente.objects.get_or_create(
                email=cliente_email,
                defaults={'nombre_completo': cliente_nombre, 'telefono': cliente_telefono}
            )
            # Si el cliente existe pero se pasó un teléfono nuevo, actualizarlo
            if not created_cliente and cliente_telefono:
                if not cliente.telefono or cliente.telefono != cliente_telefono:
                    cliente.telefono = cliente_telefono
                    cliente.save(update_fields=['telefono'])

            # 4. Verificar si ya está inscrito antes de intentar crear (opcional pero recomendado)
            if Inscripcion.objects.filter(cliente=cliente, taller=taller_locked).exists():
                return (None, False, 'Cliente ya inscrito en este taller')

            # 5. Crear inscripción
            inscripcion = Inscripcion.objects.create(
                cliente=cliente,
                taller=taller_locked,
                estado_pago='PENDIENTE'
            )

            # 6. Añadir interés automático si el taller tiene categoría
            if taller_locked.categoria:
                cliente.intereses_cliente.add(taller_locked.categoria)

            # 7. Actualizar cupos (usando el objeto bloqueado)
            taller_locked.cupos_disponibles -= 1
            taller_locked.save()

        return (inscripcion, True, 'Inscripción creada exitosamente')

    except IntegrityError:
        # Ya inscrito (por si acaso falla la verificación previa en condiciones extremas)
        return (None, False, 'Cliente ya inscrito en este taller')
    except Exception as e:
        return (None, False, f'Error inesperado: {e}')
