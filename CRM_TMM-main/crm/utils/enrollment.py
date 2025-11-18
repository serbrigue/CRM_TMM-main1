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
            cliente, created_cliente = Cliente.objects.get_or_create(
                email=cliente_email,
                defaults={'nombre_completo': cliente_nombre, 'telefono': cliente_telefono}
            )
            # Si el cliente existe pero se pasó un teléfono nuevo, actualizarlo
            if not created_cliente and cliente_telefono:
                if not cliente.telefono or cliente.telefono != cliente_telefono:
                    cliente.telefono = cliente_telefono
                    cliente.save(update_fields=['telefono'])

            # Crear inscripción; puede lanzar IntegrityError si ya existe
            inscripcion = Inscripcion.objects.create(
                cliente=cliente,
                taller=taller,
                estado_pago='PENDIENTE'
            )

            # Añadir interés automático si el taller tiene categoría
            if taller.categoria:
                cliente.intereses_cliente.add(taller.categoria)

            # Actualizar cupos de forma atómica
            Taller.objects.select_for_update().filter(id=taller.id).update(
                cupos_disponibles=F('cupos_disponibles') - 1
            )

        return (inscripcion, True, 'Inscripción creada exitosamente')

    except IntegrityError:
        # Ya inscrito
        return (None, False, 'Cliente ya inscrito en este taller')
    except Exception as e:
        return (None, False, f'Error inesperado: {e}')
