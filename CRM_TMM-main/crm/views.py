from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import F, Sum, Count, Q, Max
# Importa IntegrityError para manejo específico de errores de base de datos
from django.db import IntegrityError
from .models import Taller, Cliente, Inscripcion, Producto, Interes, DetalleVenta, VentaProducto # Asegúrate de importar los modelos de Venta
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from .forms import RegistroClienteForm
from .utils.enrollment import enroll_cliente_en_taller
from django.utils import timezone
from django.core.mail import send_mail, BadHeaderError # Importa BadHeaderError
from django.conf import settings
from decimal import Decimal
from django.db import transaction
import calendar
import datetime
from datetime import date
from django.contrib.auth.views import LoginView as DjangoLoginView
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
        # Obtener datos del form (soporta usuarios autenticados y anónimos)
        nombre = request.POST.get('nombre', '').strip()
        email = request.POST.get('email', '').strip()
        telefono = request.POST.get('telefono', '').strip()

        usuario = request.user if request.user.is_authenticated else None

        # Si el usuario no está autenticado, requerimos nombre y email
        if usuario is None and (not nombre or not email):
            messages.error(request, 'Debes ingresar tu nombre y email, o iniciar sesión.')
            return redirect('detalle_taller', taller_id=taller.id)

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
        'show_form': not request.user.is_authenticated
    }
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
            messages.success(request, '¡Registro exitoso! Bienvenido(a) a TMM.')
            return redirect('home')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = RegistroClienteForm()

    context = {
        'titulo': 'Registro de Cliente',
        'form': form,
    }
    return render(request, 'crm/registro_cliente.html', context)



def is_superuser(user):
    return user.is_superuser


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
    
    # 3. Aplicar el filtro según el parámetro
    # Se usa 'DEUDA' en lugar de 'PENDIENTE'
    if filtro_estado == 'DEUDA':
        # Filtro de "Pendientes/Abonados" (los que tienen deuda)
        inscripciones_qs = inscripciones_qs.filter(
            Q(estado_pago='PENDIENTE') | Q(estado_pago='ABONADO')
        )
    # Se usa 'PAGADO' en lugar de 'COMPLETADO'
    elif filtro_estado == 'PAGADO':
        # Filtro de "Completados" (los que no tienen deuda). Usamos 'PAGADO' como estado final.
        inscripciones_qs = inscripciones_qs.filter(estado_pago='PAGADO')
        
    # Si filtro_estado es None, se usa el .all() inicial.

    context = {
        'titulo': 'Gestión de Pagos CRM',
        'deudores': inscripciones_qs, 
        'estado_activo': filtro_estado, 
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
    ingresos_mensuales = Inscripcion.objects.filter(
        estado_pago__in=['PAGADO', 'ABONADO']
    ).annotate(
        mes_anio=TruncMonth('fecha_inscripcion')
    ).values('mes_anio').annotate(
        total_mes=Sum('monto_pagado')
    ).order_by('mes_anio')
    
    # Formato para Chart.js
    ingresos_labels = [
        f"{item['mes_anio'].strftime('%b %Y')}" for item in ingresos_mensuales
    ]
    ingresos_data = [item['total_mes'] for item in ingresos_mensuales]

    # 2. Inscripciones por Categoría (Gráfico de Dona)
    inscripciones_por_categoria = Inscripcion.objects.filter(
        estado_pago__in=['PAGADO', 'ABONADO']
    ).values('taller__categoria__nombre').annotate(
        conteo=Count('id')
    ).order_by('-conteo')

    categoria_labels = [
        item['taller__categoria__nombre'] or 'Sin Categoría' for item in inscripciones_por_categoria
    ]
    categoria_data = [item['conteo'] for item in inscripciones_por_categoria]

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
        'categoria_labels': categoria_labels,
        'categoria_data': categoria_data,
        'modalidad_labels': modalidad_labels,
        'modalidad_data': modalidad_data,
    }
    return render(request, 'crm/panel_reportes.html', context)


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

    # --- Lógica de Acción por Lote (POST) ---
    if request.method == 'POST' and 'action' in request.POST and request.POST['action'] == 'enviar_correo':
        cliente_ids = request.POST.getlist('cliente_seleccionado')
        asunto = request.POST.get('asunto_correo')
        mensaje = request.POST.get('mensaje_correo')

        if not cliente_ids:
            messages.error(request, 'Error: No seleccionaste ningún cliente.')
        elif not asunto or not mensaje:
            messages.error(request, 'Error: Debe ingresar Asunto y Mensaje para enviar el correo.')
        else:
            clientes_seleccionados = Cliente.objects.filter(id__in=cliente_ids)
            destinatarios = [c.email for c in clientes_seleccionados if c.email] # Asegurarse que tengan email
            num_seleccionados = len(cliente_ids)
            num_a_enviar = len(destinatarios)

            if num_a_enviar > 0:
                try:
                    # IMPLEMENTACIÓN REAL DE ENVÍO DE CORREO
                    mensaje_completo = f"Mensaje: {mensaje}\n\n(Nota: Este correo fue enviado a un grupo de {num_a_enviar} destinatarios.)\n"
                    send_mail(
                        subject=asunto,
                        message=mensaje_completo,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=destinatarios,
                        fail_silently=False,
                    )
                    messages.success(request, f'¡Correo simulado enviado con éxito! Se envió a {num_a_enviar} de {num_seleccionados} clientes seleccionados con el asunto: "{asunto}". Revisa la consola si usas EmailBackend.')
                except BadHeaderError:
                    messages.error(request, 'Error: Asunto inválido, contiene saltos de línea.')
                except Exception as e:
                    # Captura otros errores de envío (ej. de conexión SMTP si estuviera configurado)
                    messages.error(request, f'Error al intentar enviar el correo: {e}')
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
        'mes_calendario': mes_calendario, # La matriz de semanas y días
        'fechas_cursos_activas': fechas_cursos_activas, # Set de fechas clave (date objects)
        'mes_actual_nombre': month_name.capitalize(),
        'anio_actual': current_year,
        'current_month': current_month, # Se usa en el template para filtrar los días correctos
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
    
    for id_str, data in carrito_data.items():
        try:
            producto = Producto.objects.get(pk=int(id_str))
            cantidad = data['cantidad']
            # Convertir el precio de str a Decimal para el cálculo
            precio = Decimal(data['precio']) 
            subtotal = precio * Decimal(cantidad)
            subtotal_general += subtotal
            
            items.append({
                'producto': producto,
                'cantidad': cantidad,
                'precio_unitario': precio,
                'subtotal': subtotal,
            })
        except Producto.DoesNotExist:
            # Si el producto ya no existe, lo eliminamos del carrito
            del carrito_data[id_str]
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