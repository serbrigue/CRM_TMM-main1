from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages 
from django.db.models import F,Sum, Count, Q, Max 
from .models import Taller, Cliente, Inscripcion, Producto
from django.contrib.auth.decorators import login_required,user_passes_test
from django.db.models.functions import TruncMonth, ExtractMonth, ExtractYear
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login 
from .forms import RegistroClienteForm

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
    """
    taller = get_object_or_404(Taller, pk=taller_id)
    
    if request.method == 'POST':
        
        # 1. Validación inicial de cupos
        if taller.cupos_disponibles <= 0:
            messages.error(request, '¡Lo sentimos! Los cupos para este taller se han agotado.')
            return redirect('detalle_taller', taller_id=taller.id)

        # 2. Determinar si el cliente está autenticado o es anónimo
        if request.user.is_authenticated:
            # Opción A: Usuario Logueado
            cliente_email = request.user.email
            cliente_nombre = request.user.get_full_name() or request.user.username

            cliente, created = Cliente.objects.get_or_create(
                email=cliente_email,
                defaults={'nombre_completo': cliente_nombre}
            )
            
        else:
            # Opción B: Usuario Anónimo (Se registra con formulario)
            cliente_nombre = request.POST.get('nombre')
            cliente_email = request.POST.get('email')
            
            if not cliente_nombre or not cliente_email:
                messages.error(request, 'Debes ingresar tu nombre y email, o iniciar sesión.')
                return redirect('detalle_taller', taller_id=taller.id)
            
            cliente, created = Cliente.objects.get_or_create(
                email=cliente_email,
                defaults={'nombre_completo': cliente_nombre}
            )

        # 3. Creación Atómica de la Inscripción y Segmentación
        try:
            Inscripcion.objects.create(
                cliente=cliente,
                taller=taller,
                estado_pago='PENDIENTE' 
            )
            
            # --- LÓGICA DE SEGMENTACIÓN AUTOMÁTICA ---
            # Si el taller tiene una categoría asignada (Interes), la agregamos al perfil del cliente.
            if taller.categoria:
                # El método .add() maneja automáticamente si el interés ya existe
                cliente.intereses_cliente.add(taller.categoria) 
            # ----------------------------------------
            
            # 4. Actualización Atómica del Cupo (CRÍTICO)
            Taller.objects.filter(id=taller.id).update(cupos_disponibles=F('cupos_disponibles') - 1)

            messages.success(request, f'¡Inscripción exitosa! Cupo reservado para {taller.nombre}. Ahora puedes proceder al pago.')
            
            return redirect('pago_simulado', inscripcion_id=Inscripcion.objects.last().id) 

        except Exception:
            # Esto captura si el cliente ya está inscrito (debido al unique_together en Inscripcion)
            messages.warning(request, f'Ya estás inscrito(a) en el taller: {taller.nombre}. ¡Revisa tu correo o inicia sesión!')
            return redirect('detalle_taller', taller_id=taller.id)

    # Datos para la plantilla (Solicitud GET)
    context = {
        'titulo': f'Detalle: {taller.nombre}',
        'taller': taller,
        # Indicamos si el formulario de inscripción debe ser visible (lógica en base.html)
        'show_form': not request.user.is_authenticated 
    }
    return render(request, 'crm/detalle_taller.html', context)

def pago_simulado(request, inscripcion_id):
    """
    Vista de ejemplo para simular la página de pago después de la inscripción.
    Se utiliza el estado 'PAGADO' como estado final de pago.
    """
    inscripcion = get_object_or_404(Inscripcion, pk=inscripcion_id)
    
    # Simular que el pago se realiza con éxito al hacer POST
    if request.method == 'POST':
        # Verificamos que el estado no sea ya el estado final
        if inscripcion.estado_pago == 'PENDIENTE' or inscripcion.estado_pago == 'ABONADO':
            inscripcion.estado_pago = 'PAGADO'  # Estado de pago final completo
            inscripcion.monto_pagado = inscripcion.taller.precio # Simula pago completo
            inscripcion.save()
            messages.success(request, '¡Pago procesado con éxito! Tu cupo está 100% asegurado.')
            return redirect('home')
        else:
            messages.info(request, 'Esta inscripción ya fue pagada.')
            return redirect('home')

    context = {
        'titulo': f'Pago Pendiente: {inscripcion.taller.nombre}',
        'inscripcion': inscripcion,
    }
    return render(request, 'crm/pago_simulado.html', context)


def registro_cliente(request):
    """
    Vista para manejar el registro de nuevos clientes.
    """
    if request.method == 'POST':
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Autenticar al usuario inmediatamente después del registro
            login(request, user)
            
            messages.success(request, '¡Registro exitoso! Ya tienes una cuenta en TMM.')
            # Redirigir a una página de bienvenida o al catálogo
            return redirect('catalogo_talleres') 
        else:
            # Si el formulario no es válido (ej. email ya existe), mostrar errores
            messages.error(request, 'Error al registrar. Revisa los datos ingresados.')
    else:
        # Si es una solicitud GET, mostramos el formulario vacío
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


user_passes_test(is_superuser)
def listado_clientes(request):
    """
    Vista protegida para que la administradora vea y filtre todos los clientes registrados.
    """
    # Filtros simples de ejemplo (pueden expandirse en el futuro)
    tipo_cliente_filtro = request.GET.get('tipo', None)
    
    clientes = Cliente.objects.all().order_by('-fecha_registro')

    if tipo_cliente_filtro:
        clientes = clientes.filter(tipo_cliente=tipo_cliente_filtro)
        
    context = {
        'titulo': 'Listado de Clientes CRM',
        'clientes': clientes,
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