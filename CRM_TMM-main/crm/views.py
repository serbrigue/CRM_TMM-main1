from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import F, Sum, Count, Q, Max
# Importa IntegrityError para manejo específico de errores de base de datos
from django.db import IntegrityError
from .models import Taller, Cliente, Inscripcion, Producto, Interes, DetalleVenta, VentaProducto # Asegúrate de importar los modelos de Venta
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models.functions import TruncMonth
from django.db.models import Min, Max
import logging
import json
import math
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from .forms import RegistroClienteForm
from .utils.enrollment import enroll_cliente_en_taller
from django.utils import timezone
from django.core.mail import send_mail, BadHeaderError # Importa BadHeaderError
from django.conf import settings
from django.urls import reverse
from django.template.loader import render_to_string
from django.http import HttpResponse, JsonResponse
from decimal import Decimal, InvalidOperation
from django.db import transaction
import calendar
import datetime
from datetime import date
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.contrib.auth import logout as auth_logout


def home(request):
    """
    Función de vista para la página de inicio.
    ... (código anterior)
    """
    context = {
        'titulo': 'TMM Bienestar y Conexión',
    }
    return render(request, 'crm/home.html', context)

def catalogo_talleres(request):
    """
    Vista que muestra una lista de todos los talleres activos.
    """
    # Consulta la base de datos para obtener los talleres activos y los ordena por fecha
    talleres_activos = Taller.objects.filter(esta_activo=True).order_by('fecha_taller')
    
    context = {
        'titulo': 'Catálogo de Talleres',
        'talleres': talleres_activos,
    }
    return render(request, 'crm/catalogo_talleres.html', context)

def detalle_taller_inscripcion(request, taller_id):
    """
    Muestra la información de un taller y maneja el formulario de inscripción.
    Si la inscripción es exitosa, asigna la categoría del taller como interés al cliente.
    MEJORA: Manejo específico de IntegrityError.
    """
    taller = get_object_or_404(Taller, pk=taller_id)

    if request.method == 'POST':

        # Require authenticated user to create an enrollment
        if not request.user.is_authenticated:
            messages.error(request, 'Debes iniciar sesión para inscribirte en un taller.')
            return redirect(f"{reverse('login')}?next={request.path}")

        # Usuario autenticado: obtener teléfono opcional desde el form
        nombre = request.user.get_full_name() or request.user.username
        email = request.user.email
        telefono = request.POST.get('telefono', '').strip()

        usuario = request.user

        inscripcion, created, msg = enroll_cliente_en_taller(taller.id, nombre, email, telefono=telefono, usuario=usuario)

        if created:
            messages.success(request, f'¡Inscripción exitosa! Cupo reservado para {taller.nombre}. Ahora puedes proceder al pago.')
            return redirect('pago_simulado', inscripcion_id=inscripcion.id)
        else:
            if msg == 'No hay cupos disponibles':
                messages.error(request, '¡Lo sentimos! Los cupos para este taller se han agotado.')
            elif msg.startswith('Cliente ya inscrito'):
                messages.warning(request, f'Ya estás inscrito(a) en el taller: {taller.nombre}. ¡Revisa tu correo o inicia sesión!')
            else:
                messages.error(request, f'Ocurrió un error al inscribirte: {msg}')
            return redirect('detalle_taller', taller_id=taller.id)


    # Datos para la plantilla (Solicitud GET)
    context = {
        'titulo': f'Detalle: {taller.nombre}',
        'taller': taller,
        # Mostrar el formulario solo a usuarios autenticados
        'show_form': request.user.is_authenticated
    }
    # Si el usuario es superusuario, incluir la lista de inscripciones para mostrarla en la plantilla
    if request.user.is_superuser:
        inscripciones = Inscripcion.objects.filter(taller=taller).select_related('cliente').order_by('-fecha_inscripcion')
        context['inscripciones'] = inscripciones
    return render(request, 'crm/detalle_taller.html', context)

def pago_simulado(request, inscripcion_id):
    """
    Vista de ejemplo para simular la página de pago después de la inscripción.
    MEJORA: Añade botones para simular éxito o fallo.
    """
    inscripcion = get_object_or_404(Inscripcion, pk=inscripcion_id)

    if request.method == 'POST':
        # Determinar qué botón se presionó (si se implementan en el HTML)
        accion = request.POST.get('accion_pago', 'pagar') # Por defecto, asume pago exitoso

        if inscripcion.estado_pago == 'PAGADO':
             messages.info(request, 'Esta inscripción ya fue pagada.')
             return redirect('home')

        if accion == 'pagar':
            # Simular pago exitoso
            inscripcion.estado_pago = 'PAGADO'
            inscripcion.monto_pagado = inscripcion.taller.precio # Simula pago completo
            inscripcion.save()
            messages.success(request, '¡Pago procesado con éxito! Tu cupo está 100% asegurado.')
            return redirect('home')
        elif accion == 'fallar':
             # Simular pago fallido (opcional)
             messages.error(request, 'El pago falló. Por favor, intenta nuevamente.')
             # No cambia el estado, redirige de vuelta a la misma página
             return redirect('pago_simulado', inscripcion_id=inscripcion.id)
        # Se podrían añadir más acciones (ej. cancelar)

    context = {
        'titulo': f'Pago Pendiente: {inscripcion.taller.nombre}',
        'inscripcion': inscripcion,
    }
    return render(request, 'crm/pago_simulado.html', context)


def registro_cliente(request):
    """
    Vista para el registro de nuevos clientes.
    """
    if request.method == 'POST':
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            # Enviar correo de bienvenida usando las plantillas
            try:
                from .utils.email import send_email as send_email_util
                ctx = {
                    'nombre_cliente': usuario.get_full_name() or usuario.username,
                    'email': usuario.email,
                    'profile_url': request.build_absolute_uri(reverse('detalle_cliente_admin', args=[usuario.id])) if request.user.is_authenticated else request.build_absolute_uri('/')
                }
                text_body = render_to_string('emails/welcome.txt', ctx)
                html_body = render_to_string('emails/welcome.html', ctx)
                sender_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else None
                send_email_util(recipient=usuario.email, subject='Bienvenida a TMM', text_body=text_body, html_body=html_body, inscripcion=None, sender_name=sender_name)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.exception('Error enviando email de bienvenida: %s', e)
            messages.success(request, '¡Registro exitoso! Bienvenido(a) a TMM.')
            return redirect('home')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = RegistroClienteForm()

    context = {
        'titulo': 'Registro de Cliente',
        'form': form,
        'password_requirements': (
            'La contraseña debe tener al menos 8 caracteres, incluir una letra mayúscula, '
            'una letra minúscula y un número.'
        ),
    }
    return render(request, 'crm/registro_cliente.html', context)


class CustomLoginView(DjangoLoginView):
    """Custom LoginView que mejora la retroalimentación en fallos de inicio de sesión.

    Diferencia entre usuario inexistente y contraseña incorrecta y añade
    un error no relacionado al formulario para mostrar en la plantilla.
    """
    template_name = 'registration/login.html'

    def form_invalid(self, form):
        # Extraer el valor del campo username tal como llegó en el POST
        username_field = form.fields.get('username') if hasattr(form, 'fields') else None
        username = self.request.POST.get('username', '').strip()

        User = get_user_model()
        if username:
            try:
                User.objects.get(username=username)
                # Usuario existe -> error de contraseña
                form.add_error(None, 'Contraseña incorrecta para este usuario.')
            except User.DoesNotExist:
                # Usuario no existe
                form.add_error(None, 'El usuario no existe. Verifica el nombre de usuario o regístrate.')
        else:
            form.add_error(None, 'Debes ingresar tu nombre de usuario.')

        return super().form_invalid(form)

    def get(self, request, *args, **kwargs):
        # Consumir (leer) los mensajes previos para que no se muestren en la página de login
        # esto evita que mensajes generados en otras vistas (inscripción, pago, etc.) aparezcan aquí.
        try:
            list(messages.get_messages(request))
        except Exception:
            # Si por algún motivo la lectura falla, no bloqueamos el acceso al login
            pass
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)



def is_superuser(user):
    return user.is_superuser


@user_passes_test(is_superuser)
def gestion_talleres(request):
    """Pantalla administrativa para listar y crear talleres activos.

    Muestra tarjetas con información básica y permite crear un nuevo taller
    desde un formulario rápido.
    """
    from .forms import TallerForm

    if request.method == 'POST' and request.POST.get('action') == 'crear_taller':
        form = TallerForm(request.POST, request.FILES)
        if form.is_valid():
            taller = form.save()
            messages.success(request, f'Taller "{taller.nombre}" creado correctamente.')
            return redirect('gestion_talleres')
        else:
            messages.error(request, 'Corrige los errores del formulario al crear el taller.')
    else:
        form = TallerForm()

    talleres_activos = Taller.objects.filter(esta_activo=True).order_by('fecha_taller')

    # Filtros
    categoria_filtro = request.GET.get('categoria')
    modalidad_filtro = request.GET.get('modalidad')

    if categoria_filtro:
        talleres_activos = talleres_activos.filter(categoria__id=categoria_filtro)
    
    if modalidad_filtro:
        talleres_activos = talleres_activos.filter(modalidad=modalidad_filtro)

    context = {
        'titulo': 'Gestión de Talleres',
        'talleres': talleres_activos,
        'form': form,
    }
    return render(request, 'crm/gestion_talleres.html', context)


@user_passes_test(is_superuser)
def detalle_taller_admin(request, taller_id):
    """
    Detalle administrativo de un taller: ver inscritos, estados, filtrar y acciones masivas.
    """
    # Asegúrate de tener estos imports al inicio de tu archivo views.py
    # o descoméntalos aquí si no los tienes arriba:
    # from django.shortcuts import get_object_or_404, redirect, render
    # from django.contrib import messages
    # from django.template.loader import render_to_string
    # from django.urls import reverse
    # from .models import Taller, Inscripcion
    from .forms import TallerForm, AdminEmailForm
    
    taller = get_object_or_404(Taller, pk=taller_id)

    # ---------------------------------------------------------
    # 1. ACCIONES POST (Actualizar, Enviar Correo, Cambiar Estado)
    # ---------------------------------------------------------
    
    form = None # Inicializar variable para mantener errores si falla validación

    # A) Actualizar datos del Taller
    if request.method == 'POST' and request.POST.get('action') == 'actualizar_taller':
        form = TallerForm(request.POST, request.FILES, instance=taller)
        if form.is_valid():
            old_total = taller.cupos_totales
            taller = form.save(commit=False)
            new_total = taller.cupos_totales
            
            # Ajustar cupos_disponibles proporcionalmente
            try:
                delta = new_total - old_total
                taller.cupos_disponibles = max(0, (taller.cupos_disponibles or 0) + delta)
            except Exception:
                inscritos_count = Inscripcion.objects.filter(taller=taller).count()
                taller.cupos_disponibles = max(0, new_total - inscritos_count)
            
            taller.save()
            messages.success(request, 'Taller actualizado correctamente.')
            return redirect('detalle_taller_admin', taller_id=taller.id)
        else:
            messages.error(request, 'Errores al actualizar el taller. Revisa los datos.')

    # B) Enviar correos masivos a seleccionados
    if request.method == 'POST' and request.POST.get('action') == 'enviar_email_inscritos':
        email_form = AdminEmailForm(request.POST)
        selected = request.POST.getlist('inscripcion_sel')
        
        if not selected:
            messages.error(request, 'No seleccionaste inscritos para enviar correo.')
        elif email_form.is_valid():
            asunto = email_form.cleaned_data['asunto']
            mensaje = email_form.cleaned_data['mensaje']
            plantilla = email_form.cleaned_data.get('plantilla')
            
            inscripciones_sel = Inscripcion.objects.filter(id__in=selected).select_related('cliente')
            
            from .utils.email import send_email as send_email_util
            sender_name = request.user.get_full_name() or request.user.username
            
            successes = 0
            failures = []
            
            for ins in inscripciones_sel:
                email = ins.cliente.email if ins.cliente else None
                if not email:
                    failures.append((None, 'Sin email'))
                    continue
                
                # Preparar cuerpo del correo (Renderizar plantillas si aplica)
                if plantilla and plantilla != 'personalizado':
                    ctx = {
                        'nombre_cliente': ins.cliente.nombre_completo if ins.cliente else '',
                        'taller_nombre': taller.nombre,
                        'estado': ins.get_estado_pago_display(),
                        'pago_url': request.build_absolute_uri(reverse('pago_simulado', args=[ins.id]))
                    }
                    try:
                        text_body = render_to_string(f'emails/{plantilla}.txt', ctx)
                    except Exception:
                        text_body = mensaje
                    try:
                        html_body = render_to_string(f'emails/{plantilla}.html', ctx)
                    except Exception:
                        html_body = None
                else:
                    text_body = mensaje.replace('[Nombre del Cliente]', ins.cliente.nombre_completo if ins.cliente else '')
                    html_body = None

                ok, err = send_email_util(
                    recipient=email, 
                    subject=asunto, 
                    text_body=text_body, 
                    html_body=html_body, 
                    inscripcion=ins, 
                    sender_name=sender_name
                )
                
                if ok:
                    successes += 1
                else:
                    failures.append((email, err or 'Error desconocido'))

            if successes:
                messages.success(request, f'Correos enviados: {successes}')
            if failures:
                messages.error(request, f'Fallaron {len(failures)} envíos.')
            
            return redirect('detalle_taller_admin', taller_id=taller.id)
        else:
            messages.error(request, f'Error en el formulario de correo: {email_form.errors}')

    # C) Actualizar estado individual (Botón rápido o AJAX si implementaras)
    if request.method == 'POST' and request.POST.get('action') == 'actualizar_estado_inscripcion':
        ins_id = request.POST.get('inscripcion_id')
        nuevo_estado = request.POST.get('nuevo_estado')
        try:
            ins = Inscripcion.objects.get(id=ins_id, taller=taller)
            ins.estado_pago = nuevo_estado
            ins.save()
            messages.success(request, 'Estado de inscripción actualizado.')
        except Inscripcion.DoesNotExist:
            messages.error(request, 'Inscripción no encontrada.')
        return redirect('detalle_taller_admin', taller_id=taller.id)

    # ---------------------------------------------------------
    # 2. LOGICA GET (Filtros y Renderizado)
    # ---------------------------------------------------------
    
    # Consulta base: Traer TODOS (sin slicing [:15])
    inscripciones = Inscripcion.objects.filter(taller=taller).select_related('cliente').order_by('-fecha_inscripcion')
    
    # Filtro por Estado de Pago
    estado_filtro = request.GET.get('estado')
    if estado_filtro:
        inscripciones = inscripciones.filter(estado_pago=estado_filtro)

    # Formularios para el template
    if form is None:
        form = TallerForm(instance=taller)
        
    email_form = AdminEmailForm(initial={
        'asunto': f'Recordatorio: pago pendiente {taller.nombre}', 
        'mensaje': 'Estimado/a [Nombre del Cliente],\n\nTienes un pago pendiente...'
    })

    context = {
        'titulo': f'Administrador - Taller: {taller.nombre}',
        'taller': taller,
        'inscripciones': inscripciones,       # Lista completa o filtrada
        'inscripciones_total': inscripciones.count(),
        'form': form,
        'email_form': email_form,
        'estado_filtro': estado_filtro,       # Para mantener el select activo en el HTML
    }
    
    return render(request, 'crm/detalle_taller_admin.html', context)
# =========================================================================
# FUNCIÓN MODIFICADA PARA INCLUIR EL FILTRO DE ESTADO DE PAGO
# =========================================================================

@user_passes_test(is_superuser)
def gestion_deudores(request):
    """
    Vista protegida que muestra la lista de inscripciones, permitiendo filtrar por estado de pago.
    *** CORREGIDA PARA USAR LOS PARÁMETROS 'DEUDA' Y 'PAGADO' DE LA PLANTILLA ***
    """
    # 1. Obtener el parámetro de filtro de la URL
    filtro_estado = request.GET.get('estado', None)
    
    # 2. Iniciar el QuerySet con todas las inscripciones (para el filtro 'Todos')
    inscripciones_qs = Inscripcion.objects.all().order_by('-fecha_inscripcion')

    # --- Manejo de envío de recordatorios / cancelaciones por correo (desde la UI) ---
    if request.method == 'POST' and request.POST.get('action') in ('enviar_recordatorio', 'enviar_cancelacion'):
        action = request.POST.get('action')
        ins_ids = request.POST.getlist('inscripcion_seleccionada')
        asunto = request.POST.get('asunto_recordatorio', '').strip() or None
        mensaje = request.POST.get('mensaje_recordatorio', '').strip() or None
        template_key = request.POST.get('template_key', 'personalizado')
        # If the client didn't provide a template_key (or left it as 'personalizado')
        # but the action implies a specific template, prefer the action's template.
        if (not template_key or template_key == 'personalizado') and action == 'enviar_recordatorio':
            template_key = 'recordatorio'
        if (not template_key or template_key == 'personalizado') and action == 'enviar_cancelacion':
            template_key = 'cancelacion'

        # Defaults según acción
        if action == 'enviar_cancelacion':
            if not asunto:
                asunto = 'Cancelación de cupo - Taller TMM'
            if not mensaje:
                mensaje = 'Lamentamos informarte que tu cupo ha sido cancelado. Para más información, contacta al equipo.'
        else:
            # recordatorio
            if not asunto:
                asunto = 'Recordatorio de pago - Taller TMM'
            if not mensaje:
                mensaje = 'Te recordamos realizar el pago pendiente para confirmar tu cupo.'

        if not ins_ids:
            messages.error(request, 'Error: No seleccionaste ninguna inscripción.')
        else:
            inscripciones_sel = Inscripcion.objects.filter(id__in=ins_ids).select_related('cliente')
            destinatarios = [ins.cliente.email for ins in inscripciones_sel if ins.cliente and ins.cliente.email]
            num_seleccionados = len(ins_ids)
            num_a_enviar = len(destinatarios)

            if num_a_enviar > 0:
                # Enviar correos individualizados para evitar exponer destinatarios y permitir personalización
                successes = 0
                failures = []
                from .utils.email import send_email as send_email_util

                # Sender name: use the current logged-in user's full name or username
                sender_name = request.user.get_full_name() or request.user.username

                for ins in inscripciones_sel:
                    email = ins.cliente.email if ins.cliente else None
                    if not email:
                        failures.append((None, 'Sin email'))
                        continue
                    # Construir URL de pago (absoluta)
                    try:
                        pago_url = request.build_absolute_uri(reverse('pago_simulado', args=[ins.id]))
                    except Exception:
                        pago_url = f"/pago/{ins.id}/"
                    # If a template was chosen, render templates with context; otherwise use the free-text message
                    if template_key and template_key != 'personalizado':
                        ctx = {
                            'nombre_cliente': ins.cliente.nombre_completo if ins.cliente else '',
                            'taller_nombre': ins.taller.nombre if ins.taller else '',
                            'estado': ins.get_estado_pago_display(),
                            'pago_url': pago_url,
                        }
                        try:
                            text_body = render_to_string(f'emails/{template_key}.txt', ctx)
                        except Exception:
                            text_body = (mensaje or '').replace('[Nombre del Cliente]', ins.cliente.nombre_completo if ins.cliente else '')
                        try:
                            html_body = render_to_string(f'emails/{template_key}.html', ctx)
                        except Exception:
                            html_body = None
                    else:
                        cuerpo = mensaje or ''
                        cuerpo = cuerpo.replace('[Nombre del Cliente]', ins.cliente.nombre_completo if ins.cliente else '')
                        cuerpo = cuerpo.replace('[Taller]', ins.taller.nombre if ins.taller else '')
                        cuerpo = cuerpo.replace('[Estado]', ins.get_estado_pago_display())
                        cuerpo = cuerpo.replace('[Link de Pago Simulado]', pago_url)
                        text_body = cuerpo
                        html_body = None

                    ok, err = send_email_util(recipient=email, subject=asunto, text_body=text_body, html_body=html_body, inscripcion=ins, sender_name=sender_name)
                    if ok:
                        successes += 1
                    else:
                        failures.append((email, err or 'Error desconocido'))

                if successes:
                    messages.success(request, f'Correos enviados correctamente: {successes} de {num_seleccionados} seleccionados.')
                if failures:
                    messages.error(request, f'Fallaron {len(failures)} envíos. Ejemplos: {failures[:3]}')
            else:
                messages.error(request, 'No se encontró correo electrónico en las inscripciones seleccionadas.')

        # Tras POST redirigimos para evitar reenvío del formulario al refrescar
        return redirect('gestion_deudores')
    
    # 3. Aplicar el filtro según el parámetro
    # 'DEUDA' debe mostrar inscripciones con estado PENDIENTE (pendientes de pago)
    if filtro_estado == 'DEUDA':
        inscripciones_qs = inscripciones_qs.filter(estado_pago='PENDIENTE')
    # Nuevo filtro: mostrar inscripciones con pagos 'ABONADO' (parciales)
    elif filtro_estado == 'ABONADO':
        inscripciones_qs = inscripciones_qs.filter(estado_pago='ABONADO')
    # Se usa 'PAGADO' en lugar de 'COMPLETADO'
    elif filtro_estado == 'PAGADO':
        # Filtro de "Completados" (los que no tienen deuda). Usamos 'PAGADO' como estado final.
        inscripciones_qs = inscripciones_qs.filter(estado_pago='PAGADO')
        
    # Si filtro_estado es None, se usa el .all() inicial.

    # --- Agrupar inscripciones en lotes de 15 (índices)
    PER_PAGE = 15
    try:
        indice = int(request.GET.get('indice', 1))
    except Exception:
        indice = 1
    if indice < 1:
        indice = 1

    ins_list = list(inscripciones_qs)
    total = len(ins_list)
    num_batches = max(1, math.ceil(total / PER_PAGE))
    # Ajustar indice si excede
    if indice > num_batches:
        indice = num_batches

    start = (indice - 1) * PER_PAGE
    end = start + PER_PAGE
    current_batch = ins_list[start:end]

    # Índices para mostrar en la interfaz (evitar cálculos en la plantilla)
    if total == 0:
        mostrando_inicio = 0
        mostrando_fin = 0
    else:
        mostrando_inicio = start + 1
        mostrando_fin = min(end, total)

    # Metadatos de otros lotes
    batch_meta = []
    for i in range(1, num_batches + 1):
        s = (i - 1) * PER_PAGE + 1
        e = min(i * PER_PAGE, total)
        count = e - s + 1 if total > 0 else 0
        batch_meta.append({'indice': i, 'range': f'{s}-{e}', 'count': count})

    context = {
        'titulo': 'Gestión de Pagos CRM',
        'deudores': current_batch,
        'estado_activo': filtro_estado,
        'indice_actual': indice,
        'num_batches': num_batches,
        'batch_meta': batch_meta,
        'total_deudores': total,
        'mostrando_inicio': mostrando_inicio,
        'mostrando_fin': mostrando_fin,
    }
    return render(request, 'crm/gestion_deudores.html', context)

# =========================================================================

@user_passes_test(is_superuser)
def panel_reportes(request):
    """
    Vista protegida que solo permite el acceso a superusuarios.
    Muestra métricas y reportes analíticos.
    """
    # -----------------------------------------------------------
    # METRICAS CLAVE
    # -----------------------------------------------------------
    ingresos_totales = Inscripcion.objects.filter(
        estado_pago__in=['PAGADO', 'ABONADO']
    ).aggregate(
        total=Sum('monto_pagado')
    )['total'] or 0

    total_clientes = Cliente.objects.count()

    num_deudores = Inscripcion.objects.filter(
        estado_pago__in=['PENDIENTE', 'ABONADO']
    ).count()

    # -----------------------------------------------------------
    # REPORTES TABLA
    # -----------------------------------------------------------
    talleres_populares = Taller.objects.annotate(
        num_inscripciones=Count('inscripciones')
    ).order_by('-num_inscripciones', 'nombre')[:5]

    recaudacion_por_taller = Taller.objects.annotate(
        recaudado=Sum('inscripciones__monto_pagado', 
                      filter=Q(inscripciones__estado_pago__in=['PAGADO', 'ABONADO']))
    ).order_by('-recaudado')
    
    # -----------------------------------------------------------
    # NUEVOS DATOS PARA GRÁFICOS
    # -----------------------------------------------------------

    # 1. Ingresos por Mes (Gráfico de Líneas)
    # Construimos un rango mensual continuo entre la fecha mínima y máxima.
    # NOTA: usamos todas las inscripciones para determinar el rango temporal
    # (para que meses sin pagos aparezcan en la serie con valor 0), pero
    # calculamos los totales monetarios solo sobre inscripciones pagadas/abonadas.
    ingresos_qs = Inscripcion.objects.filter(
        estado_pago__in=['PAGADO', 'ABONADO']
    )

    rango_qs = Inscripcion.objects.all()

    # Obtener mínimo y máximo de fecha_inscripcion (basado en todas las inscripciones)
    agg_dates = rango_qs.aggregate(min_date=Min('fecha_inscripcion'), max_date=Max('fecha_inscripcion'))
    min_date = agg_dates.get('min_date')
    max_date = agg_dates.get('max_date')

    # Si no hay datos, usar el mes actual
    if not min_date or not max_date:
        now_dt = timezone.now().date()
        min_date = max_date = now_dt

    # Normalizar a primer día del mes
    start_month = date(min_date.year, min_date.month, 1)
    end_month = date(max_date.year, max_date.month, 1)

    # Generar lista de meses entre start_month y end_month inclusive
    months = []
    cur = start_month
    while cur <= end_month:
        months.append(cur)
        # avanzar un mes
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)

    # Obtener totales por mes desde la BD
    ingresos_mensuales = ingresos_qs.annotate(mes_anio=TruncMonth('fecha_inscripcion')).values('mes_anio').annotate(total_mes=Sum('monto_pagado'))
    totals_map = {}
    for item in ingresos_mensuales:
        mes_dt = item['mes_anio']
        # mes_dt puede ser datetime.date o datetime.datetime
        mes_key = date(mes_dt.year, mes_dt.month, 1)
        totals_map[mes_key] = item['total_mes'] or 0

    # Rellenar la serie con 0 donde no hay datos
    ingresos_labels = [m.strftime('%b %Y') for m in months]
    ingresos_data = [float(totals_map.get(m, 0)) for m in months]
    # Metadata para redirección (Mes y Año)
    ingresos_meta = [{'mes': m.month, 'anio': m.year} for m in months]

    # Log para depuración: ver en logs del contenedor qué serie se está enviando
    logger = logging.getLogger(__name__)
    try:
        logger.info('INGRESOS_SERIE labels=%s data=%s', json.dumps(ingresos_labels), json.dumps(ingresos_data))
    except Exception:
        logger.info('INGRESOS_SERIE no pudo serializar datos')
    # Print directo para asegurar salida en logs del contenedor
    try:
        print('INGRESOS_SERIE', json.dumps(ingresos_labels), json.dumps(ingresos_data))
    except Exception:
        print('INGRESOS_SERIE: error al serializar datos')

    # 2. Inscripciones por Categoría (Gráfico de Dona)
    inscripciones_por_categoria = Inscripcion.objects.filter(
        estado_pago__in=['PAGADO', 'ABONADO']
    ).values('taller__categoria__nombre', 'taller__categoria__id').annotate(
        conteo=Count('id')
    ).order_by('-conteo')

    categoria_labels = [
        item['taller__categoria__nombre'] or 'Sin Categoría' for item in inscripciones_por_categoria
    ]
    categoria_data = [item['conteo'] for item in inscripciones_por_categoria]
    categoria_ids = [item['taller__categoria__id'] for item in inscripciones_por_categoria]

    # 3. Inscripciones por Modalidad (Gráfico de Barras)
    inscripciones_por_modalidad = Inscripcion.objects.filter(
        estado_pago__in=['PAGADO', 'ABONADO']
    ).values('taller__modalidad').annotate(
        conteo=Count('id')
    ).order_by('-conteo')

    modalidad_labels = [
        # Traducir los códigos a nombres legibles
        'PRESENCIAL' if item['taller__modalidad'] == 'PRESENCIAL' else 'ONLINE'
        for item in inscripciones_por_modalidad
    ]
    modalidad_data = [item['conteo'] for item in inscripciones_por_modalidad]
    modalidad_keys = [item['taller__modalidad'] for item in inscripciones_por_modalidad]

    # 4. Ingresos por Categoría (Gráfico de Barras)
    ingresos_por_categoria = Inscripcion.objects.filter(
        estado_pago__in=['PAGADO', 'ABONADO']
    ).values('taller__categoria__nombre', 'taller__categoria__id').annotate(
        total=Sum('monto_pagado')
    ).order_by('-total')

    ingresos_categoria_labels = [
        item['taller__categoria__nombre'] or 'Sin Categoría' for item in ingresos_por_categoria
    ]
    ingresos_categoria_data = [float(item['total'] or 0) for item in ingresos_por_categoria]
    ingresos_categoria_ids = [item['taller__categoria__id'] for item in ingresos_por_categoria]

    context = {
        'titulo': 'Panel de Reportes y Análisis CRM',
        'ingresos_totales': ingresos_totales,
        'total_clientes': total_clientes,
        'talleres_populares': talleres_populares,
        'recaudacion_por_taller': recaudacion_por_taller,
        'num_deudores': num_deudores,

        # DATOS PARA GRÁFICOS
        'ingresos_labels': ingresos_labels,
        'ingresos_data': ingresos_data,
        'ingresos_meta': ingresos_meta,
        'categoria_labels': categoria_labels,
        'categoria_data': categoria_data,
        'categoria_ids': categoria_ids,
        'modalidad_labels': modalidad_labels,
        'modalidad_data': modalidad_data,
        'modalidad_keys': modalidad_keys,
        'ingresos_categoria_labels': ingresos_categoria_labels,
        'ingresos_categoria_data': ingresos_categoria_data,
        'ingresos_categoria_ids': ingresos_categoria_ids,
    }
    return render(request, 'crm/panel_reportes.html', context)

@user_passes_test(is_superuser)
def desglose_ingresos(request):
    """
    Vista para ver el detalle de los ingresos con filtros.
    """
    from .models import Interes # Importar aquí o arriba si es necesario

    # Filtros
    mes_filtro = request.GET.get('mes')
    anio_filtro = request.GET.get('anio')
    categoria_filtro = request.GET.get('categoria')

    inscripciones = Inscripcion.objects.filter(
        estado_pago__in=['PAGADO', 'ABONADO']
    ).select_related('cliente', 'taller', 'taller__categoria').order_by('-fecha_inscripcion')

    if mes_filtro:
        inscripciones = inscripciones.filter(fecha_inscripcion__month=mes_filtro)
    
    if anio_filtro:
        inscripciones = inscripciones.filter(fecha_inscripcion__year=anio_filtro)
    
    if categoria_filtro:
        inscripciones = inscripciones.filter(taller__categoria__id=categoria_filtro)

    total_filtrado = inscripciones.aggregate(total=Sum('monto_pagado'))['total'] or 0

    # Datos para los selectores
    categorias = Interes.objects.all().order_by('nombre')
    
    # Generar lista de años disponibles (basado en datos reales)
    anios_disponibles = Inscripcion.objects.dates('fecha_inscripcion', 'year')
    anios = [d.year for d in anios_disponibles]
    # Asegurar que el año actual esté si no hay datos
    current_year = timezone.now().year
    if current_year not in anios:
        anios.append(current_year)
    anios = sorted(list(set(anios)), reverse=True)

    meses = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]

    context = {
        'titulo': 'Desglose de Ingresos',
        'inscripciones': inscripciones,
        'total_filtrado': total_filtrado,
        'categorias': categorias,
        'meses': meses,
        'anios': anios,
        'mes_filtro': mes_filtro,
        'anio_filtro': anio_filtro,
        'categoria_filtro': categoria_filtro,
    }
    return render(request, 'crm/desglose_ingresos.html', context)


@user_passes_test(is_superuser)
def listado_clientes(request):
    """
    Vista protegida para que la administradora vea y filtre todos los clientes registrados.
    Permite filtrar por tipo de cliente, intereses (múltiples) y talleres a asistir.
    Permite la gestión de correos por lote.
    MEJORA: Manejo de errores en envío de correo.
    """
    # 1. Filtros y Variables (Lógica GET - se mantiene igual)
    tipo_cliente_filtro = request.GET.get('tipo', None)
    intereses_filtro = request.GET.getlist('interes', [])
    taller_asistir_filtro = request.GET.get('taller_asistir', None)
    deudores_filtro = request.GET.get('deudores', None)

    clientes = Cliente.objects.all().order_by('-fecha_registro')

    # --- Lógica de Filtrado (Se mantiene igual) ---
    if tipo_cliente_filtro:
        clientes = clientes.filter(tipo_cliente=tipo_cliente_filtro)
    if intereses_filtro:
        # Asegurarse que los IDs son números antes de filtrar
        interes_ids_int = [int(i) for i in intereses_filtro if i.isdigit()]
        if interes_ids_int:
            clientes = clientes.filter(intereses_cliente__id__in=interes_ids_int).distinct()
    if taller_asistir_filtro and taller_asistir_filtro.isdigit():
        taller_id = int(taller_asistir_filtro)
        clientes = clientes.filter(
            inscripciones__taller__id=taller_id,
            inscripciones__estado_pago__in=['PENDIENTE', 'ABONADO', 'PAGADO']
        ).distinct()
    
    if deudores_filtro == 'true':
        clientes = clientes.filter(
            inscripciones__estado_pago__in=['PENDIENTE', 'ABONADO']
        ).distinct()

    # --- Lógica de Acción por Lote (POST) ---
    if request.method == 'POST' and 'action' in request.POST and request.POST['action'] == 'enviar_correo':
        cliente_ids = request.POST.getlist('cliente_seleccionado')
        asunto = request.POST.get('asunto_correo')
        mensaje = request.POST.get('mensaje_correo')
        template_key = request.POST.get('template_key', 'personalizado')

        # If template is selected, allow empty mensaje (we'll render the template server-side).
        if not cliente_ids:
            messages.error(request, 'Error: No seleccionaste ningún cliente.')
        elif template_key == 'personalizado' and (not asunto or not mensaje):
            messages.error(request, 'Error: Debe ingresar Asunto y Mensaje para enviar el correo.')
        else:
            clientes_seleccionados = Cliente.objects.filter(id__in=cliente_ids)
            destinatarios = [c.email for c in clientes_seleccionados if c.email] # Asegurarse que tengan email
            num_seleccionados = len(cliente_ids)
            num_a_enviar = len(destinatarios)

            if num_a_enviar > 0:
                from .utils.email import send_email as send_email_util

                # Determine sender name (use currently logged-in user's full name or username)
                sender_name = request.user.get_full_name() or request.user.username

                successes = 0
                failures = []

                # Prepare filter-based placeholders: if a taller or intereses filter is active, compute their readable values
                intereses_names = []
                if intereses_filtro:
                    intereses_qs = Interes.objects.filter(id__in=[int(i) for i in intereses_filtro if i.isdigit()])
                    intereses_names = [i.nombre for i in intereses_qs]

                taller_name = None
                if taller_asistir_filtro and taller_asistir_filtro.isdigit():
                    try:
                        t = Taller.objects.get(id=int(taller_asistir_filtro))
                        taller_name = t.nombre
                    except Taller.DoesNotExist:
                        taller_name = None

                for c in clientes_seleccionados:
                    email = c.email
                    if not email:
                        failures.append((None, 'Sin email'))
                        continue
                    # Determine message bodies based on template selection
                    if template_key != 'personalizado':
                        # render templates with context
                        ctx = {
                            'nombre_cliente': c.nombre_completo or '',
                            'taller_nombre': taller_name or '',
                            'intereses': intereses_names,
                            'estado': '',
                            'pago_url': request.build_absolute_uri('/')
                        }
                        text_body = render_to_string(f'emails/{template_key}.txt', ctx)
                        html_body = render_to_string(f'emails/{template_key}.html', ctx)
                    else:
                        text_body = (mensaje or '').replace('[Nombre del Cliente]', c.nombre_completo or '')
                        if '[Intereses]' in text_body and intereses_names:
                            text_body = text_body.replace('[Intereses]', ', '.join(intereses_names))
                        if '[Taller]' in text_body and taller_name:
                            text_body = text_body.replace('[Taller]', taller_name)
                        html_body = None

                    ok, err = send_email_util(recipient=email, subject=asunto, text_body=text_body, html_body=html_body, inscripcion=None, sender_name=sender_name)
                    if ok:
                        successes += 1
                    else:
                        failures.append((email, err or 'Error desconocido'))

                if successes:
                    messages.success(request, f'Correos enviados correctamente: {successes} de {num_seleccionados} seleccionados.')
                if failures:
                    messages.error(request, f'Fallaron {len(failures)} envíos. Ejemplos: {failures[:3]}')
            else:
                 messages.warning(request, f'Se seleccionaron {num_seleccionados} clientes, pero ninguno tenía una dirección de correo válida registrada.')

        # Redirigir siempre después de un POST para evitar reenvíos, manteniendo los filtros GET
        url_params = request.GET.urlencode()
        return redirect(f'{request.path}?{url_params}')

    # --- Contexto para la plantilla (GET) ---
    todos_intereses = Interes.objects.all().order_by('nombre')
    talleres_futuros = Taller.objects.filter(
        esta_activo=True,
        fecha_taller__gte=timezone.now().date()
    ).order_by('fecha_taller')

    context = {
        'titulo': 'Listado de Clientes CRM',
        'clientes': clientes,
        'todos_intereses': todos_intereses,
        'intereses_activos': [int(i) for i in intereses_filtro if i.isdigit()],
        'talleres_futuros': talleres_futuros,
        'taller_asistir_activo': int(taller_asistir_filtro) if taller_asistir_filtro and taller_asistir_filtro.isdigit() else None,
    }
    return render(request, 'crm/listado_clientes.html', context)


@user_passes_test(is_superuser)
def detalle_cliente_admin(request, cliente_id):
    """
    Vista protegida para ver todos los datos, historial y notas de seguimiento de un cliente.
    """
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    
    # Obtener el historial de talleres y el total de talleres
    historial_inscripciones = cliente.inscripciones.all().order_by('-taller__fecha_taller')
    total_talleres_realizados = historial_inscripciones.count()

    context = {
        'titulo': f'Detalle de Cliente: {cliente.nombre_completo}',
        'cliente': cliente,
        'historial_inscripciones': historial_inscripciones,
        'total_talleres_realizados': total_talleres_realizados,
        # Aquí se podrían agregar las notas de seguimiento en un paso posterior
    }
    return render(request, 'crm/detalle_cliente_admin.html', context)


@user_passes_test(is_superuser)
def email_preview(request):
    """Render a preview of an email template for AJAX requests.

    Expects POST with: template_key, sample_name, sample_taller_id (optional)
    Returns rendered HTML snippet.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)

    template_key = request.POST.get('template_key')
    sample_name = request.POST.get('sample_name', 'Cliente Ejemplo')
    sample_taller_id = request.POST.get('sample_taller_id')

    taller_nombre = ''
    if sample_taller_id and sample_taller_id.isdigit():
        try:
            taller = Taller.objects.get(id=int(sample_taller_id))
            taller_nombre = taller.nombre
        except Taller.DoesNotExist:
            taller_nombre = ''

    ctx = {
        'nombre_cliente': sample_name,
        'taller_nombre': taller_nombre,
        'estado': 'Pago Pendiente',
        'pago_url': request.build_absolute_uri('/')
    }

    try:
        html = render_to_string(f'emails/{template_key}.html', ctx)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

    return HttpResponse(html)

def catalogo_productos(request):
    """
    Vista que muestra una lista de todos los Kits/Productos disponibles para la venta.
    """
    # Filtra solo los productos que están marcados como disponibles
    productos_disponibles = Producto.objects.filter(esta_disponible=True).order_by('nombre')
    
    context = {
        'titulo': 'Catálogo de Kits y Productos',
        'productos': productos_disponibles,
    }
    return render(request, 'crm/catalogo_productos.html', context)

def detalle_producto(request, producto_id):
    """
    Muestra la información de un Kit/Producto específico.
    """
    producto = get_object_or_404(Producto, pk=producto_id)
    
    context = {
        'titulo': f'Detalle de Kit: {producto.nombre}',
        'producto': producto,
    }
    # NOTA: En un proyecto completo, aquí se manejaría el formulario "Añadir al Carrito"
    return render(request, 'crm/detalle_producto.html', context)

@login_required 
def perfil_usuario(request):
    """
    Vista protegida que muestra el perfil, información personal y historial 
    de inscripciones/compras del cliente actual.
    INCLUYE RECOMENDACIONES DE TALLERES Y DATOS PARA EL CALENDARIO.
    """
    try:
        # 1. Obtener el objeto Cliente asociado al usuario autenticado
        cliente = Cliente.objects.get(email=request.user.email)
    except Cliente.DoesNotExist:
        cliente = None 
        messages.warning(request, "Tu perfil de cliente aún no ha sido creado. Inscríbete a un taller para completarlo.")
        
    historial_inscripciones = None
    historial_compras = None
    talleres_recomendados = None 
    fechas_cursos_activas = set() 
    
    # 3. Lógica del Calendario: Obtener las fechas de los cursos
    today = timezone.localdate()
    current_year = today.year
    current_month = today.month
    
    if cliente:
        # Historial (solo inscripciones que impliquen asistencia/pago)
        historial_inscripciones = cliente.inscripciones.all().order_by('-taller__fecha_taller')
        historial_compras = cliente.compras_kits.all().order_by('-fecha_venta')

        # Obtener todas las fechas de los talleres pagados/pendientes/abonados (futuros o de hoy)
        fechas_raw = cliente.inscripciones.filter(
            estado_pago__in=['PENDIENTE', 'PAGADO', 'ABONADO'],
            taller__fecha_taller__gte=today 
        ).values_list('taller__fecha_taller', flat=True)
        
        # Almacenar las fechas en un set para búsqueda rápida
        fechas_cursos_activas = {f for f in fechas_raw}
        
        # --- LÓGICA CORREGIDA PARA SELECCIONAR EL MES ---
        # 1. Verificar si hay cursos en el mes actual (incluyendo el año)
        cursos_en_mes_actual = [
            f for f in fechas_cursos_activas 
            if f.month == today.month and f.year == today.year
        ]
        
        if not cursos_en_mes_actual and fechas_cursos_activas:
            # 2. Si NO hay cursos en el mes actual, pero sí hay cursos futuros,
            #    saltamos al mes del curso más próximo (el que antes te saltaba a 2025).
            proxima_fecha = min(fechas_cursos_activas)
            current_year = proxima_fecha.year
            current_month = proxima_fecha.month
        # Si hay cursos en el mes actual, se mantiene el mes actual por defecto.
        # ------------------------------------------------

        # Lógica de Recomendación 
        intereses_cliente = cliente.intereses_cliente.all()
        
        if intereses_cliente.exists():
            interes_ids = [interes.id for interes in intereses_cliente]
            talleres_recomendados = Taller.objects.filter(
                esta_activo=True, 
                fecha_taller__gte=today,
                categoria__id__in=interes_ids 
            ).exclude(
                inscripciones__cliente=cliente 
            ).distinct().order_by('fecha_taller')[:4]
        
    # 4. Construir la matriz del calendario para la plantilla
    cal = calendar.Calendar()
    # Usa el mes y año determinado por la lógica de arriba
    mes_calendario = cal.monthdatescalendar(current_year, current_month)
    
    # 5. Mapear los nombres de los meses a español
    month_name = datetime.date(current_year, current_month, 1).strftime('%B')
    
    context = {
        'titulo': f'Perfil de {request.user.first_name}',
        'cliente': cliente,
        'user_django': request.user, 
        'historial_inscripciones': historial_inscripciones,
        'historial_compras': historial_compras,
        'talleres_recomendados': talleres_recomendados,
        # --- DATOS DEL CALENDARIO ---
        'mes_calendario': mes_calendario # La matriz de semanas y días
        ,'fechas_cursos_activas': fechas_cursos_activas # Set de fechas clave (date objects)
        ,'mes_actual_nombre': month_name.capitalize()
        ,'anio_actual': current_year
        ,'current_month': current_month # Se usa en el template para filtrar los días correctos
        # ----------------------------
    }
    
    return render(request, 'crm/profile.html', context)



def get_carrito(request):
    """Obtiene el carrito de la sesión. Si no existe, lo inicializa."""
    if 'carrito' not in request.session:
        # Estructura del carrito: { 'producto_id': {'cantidad': X, 'precio': Y} }
        request.session['carrito'] = {}
    return request.session['carrito']

def guardar_carrito(request, carrito):
    """Guarda el carrito actualizado en la sesión."""
    request.session['carrito'] = carrito
    # Marcar la sesión como modificada para asegurar que se guarde en la base de datos
    request.session.modified = True 

def agregar_a_carrito(request, producto_id):
    """Añade un producto al carrito, manejando el incremento de cantidad."""
    producto = get_object_or_404(Producto, pk=producto_id, esta_disponible=True)
    carrito = get_carrito(request)

    # Se usa str(producto_id) porque las claves de sesión deben ser strings
    producto_id_str = str(producto_id)

    if producto_id_str in carrito:
        carrito[producto_id_str]['cantidad'] += 1
    else:
        carrito[producto_id_str] = {
            'cantidad': 1,
            # Almacenamos el precio de venta actual del producto en el carrito
            'precio': str(producto.precio_venta), 
        }

    guardar_carrito(request, carrito)
    messages.success(request, f'"{producto.nombre}" agregado al carrito.')
    return redirect('ver_carrito')


def actualizar_carrito(request):
    """Actualiza o elimina items del carrito basado en el formulario POST."""
    if request.method == 'POST':
        carrito = get_carrito(request)
        
        producto_id = request.POST.get('producto_id')
        nueva_cantidad = request.POST.get('cantidad')
        
        if producto_id in carrito:
            try:
                nueva_cantidad = int(nueva_cantidad)
                
                if nueva_cantidad > 0:
                    carrito[producto_id]['cantidad'] = nueva_cantidad
                    messages.success(request, 'Cantidad actualizada.')
                else:
                    del carrito[producto_id]
                    messages.warning(request, 'Producto eliminado del carrito.')
                    
                guardar_carrito(request, carrito)
                
            except ValueError:
                messages.error(request, 'Cantidad inválida.')
        
    return redirect('ver_carrito')


def ver_carrito(request):
    """Muestra el contenido detallado del carrito."""
    carrito_data = get_carrito(request)
    
    # Lista para almacenar los objetos Producto y sus datos del carrito
    items = []
    subtotal_general = Decimal(0)
    
    # Iterar sobre una copia de los items para evitar modificar el dict durante la iteración
    keys_to_remove = []
    for id_str, data in list(carrito_data.items()):
        try:
            producto = Producto.objects.get(pk=int(id_str))
            cantidad = int(data.get('cantidad', 0))
            # Convertir el precio de str a Decimal para el cálculo
            precio = Decimal(str(data.get('precio', '0'))) 
            subtotal = precio * Decimal(cantidad)
            subtotal_general += subtotal;

            items.append({
                'producto': producto,
                'cantidad': cantidad,
                'precio_unitario': precio,
                'subtotal': subtotal,
            })
        except Producto.DoesNotExist:
            # Si el producto ya no existe, marcar para eliminarlo después
            keys_to_remove.append(id_str)
        except (ValueError, InvalidOperation):
            # Datos corruptos en sesión; marcar para eliminación
            keys_to_remove.append(id_str)

    # Eliminar las claves inválidas fuera del bucle de iteración y guardar sólo si hubo cambios
    if keys_to_remove:
        for k in keys_to_remove:
            carrito_data.pop(k, None)
        guardar_carrito(request, carrito_data)
            
    context = {
        'titulo': 'Mi Carrito de Compras',
        'items': items,
        'subtotal_general': subtotal_general,
        'impuesto': Decimal(0), # TMM no mencionó IVA/impuestos. Dejar en 0.
        'total_final': subtotal_general,
    }
    return render(request, 'crm/carrito.html', context)

@transaction.atomic # --- Mantenemos la transacción atómica ---
def finalizar_compra(request):
    """Procesa el pago y registra la venta y detalles. REQUIERE AUTENTICACIÓN."""
    if not request.user.is_authenticated:
        messages.warning(request, 'Debes iniciar sesión o registrarte para completar la compra.')
        return redirect('login') 

    carrito_data = get_carrito(request)
    if not carrito_data:
        messages.error(request, 'El carrito está vacío.')
        return redirect('ver_carrito')

    # 1. Obtener el cliente
    try:
        cliente = Cliente.objects.get(email=request.user.email)
    except Cliente.DoesNotExist:
        cliente, _ = Cliente.objects.get_or_create(
            email=request.user.email,
            defaults={'nombre_completo': request.user.get_full_name() or request.user.username}
        )

    # --- NUEVO: PASO 2 - VALIDACIÓN DE STOCK ANTES DE COBRAR ---
    # Revisamos todo el carrito antes de tocar la base de datos
    for id_str, data in carrito_data.items():
        try:
            producto = Producto.objects.get(pk=int(id_str))
            cantidad_solicitada = data['cantidad']
            
            # Comparamos con el stock_actual del modelo Producto
            if producto.stock_actual < cantidad_solicitada:
                messages.error(request, f'¡Stock insuficiente! Solo quedan {producto.stock_actual} unidades de "{producto.nombre}".')
                return redirect('ver_carrito')
        except Producto.DoesNotExist:
            messages.error(request, f'El producto con ID {id_str} ya no existe.')
            # (Opcional: eliminarlo del carrito aquí)
            return redirect('ver_carrito')
    # --- FIN DE LA VALIDACIÓN ---


    # 3. Registrar la Venta (VentaProducto)
    # (El código anterior se mueve del paso 2 al 3)
    venta = VentaProducto.objects.create(
        cliente=cliente,
        monto_total=Decimal(0), 
        estado_pago='PENDIENTE' 
    )

    subtotal_general = Decimal(0)
    
    # 4. Registrar Detalles y Actualizar Stock
    for id_str, data in carrito_data.items():
        # Volvemos a obtener el producto (dentro de la transacción)
        producto = get_object_or_404(Producto, pk=int(id_str))
        cantidad = data['cantidad']
        precio_unitario = Decimal(data['precio'])
        subtotal = precio_unitario * Decimal(cantidad)
        subtotal_general += subtotal

        # --- MODIFICADO: Actualizar Stock Atómicamente ---
        # Usamos F() para evitar condiciones de carrera (race conditions)
        producto.stock_actual = F('stock_actual') - cantidad
        producto.save(update_fields=['stock_actual']) 
        # --------------------------------------------------

        DetalleVenta.objects.create(
            venta=venta,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
        )

    # 5. Actualizar Monto Total y marcar como PAGADO (Simulación)
    venta.monto_total = subtotal_general
    venta.estado_pago = 'PAGADO' 
    venta.save()
    
    # 6. Limpiar Carrito y Mensaje
    del request.session['carrito']
    request.session.modified = True
    
    messages.success(request, f'¡Compra finalizada y pagada con éxito! Total: ${venta.monto_total} CLP.')
    return redirect('home')

# Modificar Detalle Producto para permitir agregar al carrito
def detalle_producto(request, producto_id):
    """
    Muestra la información de un Kit/Producto específico.
    """
    producto = get_object_or_404(Producto, pk=producto_id)
    
    context = {
        'titulo': f'Detalle de Kit: {producto.nombre}',
        'producto': producto,
    }
    # NOTA: La plantilla tendrá el botón para agregar al carrito
    return render(request, 'crm/detalle_producto.html', context)

def logout(request):
    """Cierra la sesión del usuario y redirige a la página de inicio."""
    auth_logout(request)
    messages.info(request, 'Has cerrado sesión exitosamente.')
    return redirect('home')