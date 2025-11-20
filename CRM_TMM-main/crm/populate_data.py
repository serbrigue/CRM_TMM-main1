# crm/populate_data.py
import os
import django
import sys # <-- AÑADE ESTA LÍNEA AL INICIO DE TUS IMPORTS
from django.db import transaction # <-- AÑADE ESTA LÍNEA

# --- Configuración de Django (ASEGÚRATE DE EJECUTAR ESTO DESDE LA RAÍZ DEL PROYECTO) ---
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_path) # <-- ¡LÍNEA DESCOMENTADA!
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tmm_project.settings')
django.setup()
# --- Fin Configuración ---

import datetime
import random
from decimal import Decimal
from django.db.utils import IntegrityError
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import F
from datetime import date

# Importar tus modelos (asegúrate que Empresa esté importado)
from crm.models import Interes, Cliente, Taller, Inscripcion, Producto, VentaProducto, DetalleVenta, Empresa

# --- VARIABLES DE AYUDA Y NOMBRES (sin cambios) ---
NOMBRES_FEMENINOS = ["Jessica", "Pamela", "Angélica", "Daniela", "Cynthia", "Marisol", "Nataly", "Fernanda", "Sara", "Gloria", "Carla", "Maleni", "Noemi", "Rosa"]
APELLIDOS = ["Vargas", "López", "Gómez", "Díaz", "Escobar", "Ibaeta", "Barrera", "González", "Sánchez", "Muñoz"]
COMUNAS = ["Valparaíso", "Viña del Mar", "Quilpué", "Villa Alemana"]
CANALES = ['INSTAGRAM', 'WHATSAPP', 'FACEBOOK', 'RECOMENDACION']

# --- FUNCIONES DE AYUDA (sin cambios) ---
def get_random_date(start_year, end_year):
    """Genera una fecha de nacimiento aleatoria entre dos años."""
    start_date = datetime.date(start_year, 1, 1)
    end_date = datetime.date(end_year, 12, 31)
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    if days_between_dates <= 0: return start_date # Evita error si start_year >= end_year
    random_number_of_days = random.randrange(days_between_dates)
    return start_date + datetime.timedelta(days=random_number_of_days)

def get_random_datetime(days_ago_min, days_ago_max):
    """Genera un datetime aleatorio en el pasado."""
    now = timezone.now()
    start_time = now - datetime.timedelta(days=days_ago_max)
    end_time = now - datetime.timedelta(days=days_ago_min)
    if start_time >= end_time: return end_time # Evita error si min >= max
    time_diff = end_time - start_time
    random_seconds = random.randrange(int(time_diff.total_seconds()))
    return start_time + datetime.timedelta(seconds=random_seconds)


def get_random_date_between(start_date, end_date):
    """Genera una fecha aleatoria entre dos fechas (incluye ambos extremos)."""
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    days_between = (end_date - start_date).days
    if days_between <= 0:
        return start_date
    return start_date + datetime.timedelta(days=random.randint(0, days_between))


def get_random_datetime_between(start_dt, end_dt):
    """Genera un datetime aleatorio entre dos datetimes (incluye ambos extremos)."""
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt
    delta = end_dt - start_dt
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return start_dt
    return start_dt + datetime.timedelta(seconds=random.randint(0, total_seconds))

def clean_database():
    """Elimina todos los datos de los modelos de prueba para empezar limpio."""
    print("Limpiando la base de datos...")
    DetalleVenta.objects.all().delete()
    VentaProducto.objects.all().delete()
    Producto.objects.all().delete()
    Inscripcion.objects.all().delete()
    Taller.objects.all().delete()
    # Eliminar Clientes y luego Empresas para evitar problemas de FK
    Cliente.objects.all().delete()
    Empresa.objects.all().delete() # Limpiar empresas también
    Interes.objects.all().delete()
    User.objects.filter(is_superuser=False).delete() # Borra todos menos superusuarios
    print("Limpieza completada.")


def populate_initial_data():
    """Crea los datos de prueba B2B y B2C."""

    clean_database()
    print("Iniciando población de datos B2B/B2C...")

    # --- 1. INTERESES (CATEGORÍAS) ---
    print("\n1. Creando Intereses...")
    intereses_data = [
        ('Resina', 50000),
        ('Encuadernación', 40000),
        ('Timbres y Estampados', 25000),
        ('Cajas y Regalo', 30000),
        ('Bienestar Corporativo', 250000)
    ]
    intereses_map = {}
    precios_base = {}
    for nombre, precio_base in intereses_data:
        interes_obj = Interes.objects.create(nombre=nombre, descripcion=f"Interés principal en {nombre}.")
        intereses_map[nombre] = interes_obj
        precios_base[nombre] = Decimal(precio_base)
    intereses_b2c_list = [intereses_map[n] for n in intereses_map if n != 'Bienestar Corporativo']

    # --- 2. SUPERUSUARIO ---
    print("2. Creando Superusuario (si no existe)...")
    if not User.objects.filter(username='admin_tmm').exists():
        User.objects.create_superuser('admin_tmm', 'carolina@tmm.cl', 'adminpass')

    # --- 3. EMPRESAS B2B (3 Empresas) ---
    print("3. Creando Empresas B2B...")
    empresas_list = []
    for i in range(1, 4):
        rut_empresa = f"{random.randint(70, 99)}{random.randint(100, 999)}{random.randint(100, 999)}-{random.randint(0, 9)}"
        empresa = Empresa.objects.create(
            razon_social=f"Empresa de Prueba #{i} SPA",
            rut=rut_empresa,
            telefono_empresa=f'+562{random.randint(10000000, 99999999)}',
            direccion=f"Calle Ficticia {random.randint(100, 999)}, {random.choice(['Santiago', 'Valparaíso'])}"
        )
        empresas_list.append(empresa)

    # --- 4. CLIENTES (40 Contactos: 37 B2C, 3 B2B asociados a Empresas) ---
    print("4. Creando Contactos (Clientes) B2C y B2B...")
    clientes_list = []

    # 4.1. Contactos B2C (37)
    for i in range(1, 38):
        nombre = random.choice(NOMBRES_FEMENINOS)
        apellido = random.choice(APELLIDOS)
        email = f'cliente_b2c_{i}_{random.randint(100,999)}@testmail.com'
        telefono = f'+569{random.randint(10000000, 99999999)}'
        username = f'usuario_b2c_{i}' # Cambiado para evitar colisión si se corre varias veces

        try:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email, 'first_name': nombre, 'last_name': apellido}
            )
            if created:
                user.set_password('password123')
                user.save()
        except IntegrityError: # Si el email ya existe con otro user, genera uno nuevo
             email = f'cliente_b2c_{i}_{random.randint(1000,9999)}@testmail-alt.com'
             user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email, 'first_name': nombre, 'last_name': apellido}
             )
             if created:
                 user.set_password('password123')
                 user.save()


        cliente = Cliente.objects.create(
            nombre_completo=f'{nombre} {apellido}',
            email=email,
            telefono=telefono,
            fecha_nacimiento=get_random_date(1985, 2005), # Rango de edad ampliado
            comuna_vive=random.choice(COMUNAS),
            tipo_cliente='B2C',
            observaciones=f"Cliente B2C #{i}. Contactado por {random.choice(CANALES)}."
            # empresa se deja en None por defecto
        )
        cliente.intereses_cliente.set(random.sample(intereses_b2c_list, random.randint(1, 2)))
        clientes_list.append(cliente)

    # 4.2. Contactos B2B (3, uno por empresa)
    for i, empresa_obj in enumerate(empresas_list, 1):
        nombre_contacto = random.choice(["Andrea", "Javier", "Marcela"]) # Nombres comunes en RRHH
        apellido_contacto = random.choice(APELLIDOS)
        email_contacto = f'contacto_{i}@empresa{i}.test'
        telefono_contacto = f'+569{random.randint(10000000, 99999999)}'

        # No creamos User para contactos B2B en este ejemplo, podrían no necesitar login
        cliente = Cliente.objects.create(
            nombre_completo=f"{nombre_contacto} {apellido_contacto}",
            email=email_contacto,
            telefono=telefono_contacto,
            tipo_cliente='B2B',
            empresa=empresa_obj, # Vinculamos el contacto a la empresa
            observaciones=f"Contacto principal de RRHH para {empresa_obj.razon_social}."
        )
        cliente.intereses_cliente.add(intereses_map['Bienestar Corporativo'])
        clientes_list.append(cliente)


    # --- 5. TALLERES (7 Talleres - Lógica sin cambios significativos) ---
    print("5. Creando Talleres...")
    talleres_list = []
    # Año actual para crear históricos y futuros relativos al año en ejecución
    current_year = timezone.now().year
    # Taller B2B
    taller_b2b_obj = Taller.objects.create(
        nombre='Taller Autocuidado Corporativo',
        descripcion='Sesión de manualidades y bienestar para equipos.',
        precio=precios_base['Bienestar Corporativo'],
        cupos_totales=10000,
        categoria=intereses_map['Bienestar Corporativo'],
        fecha_taller=date( current_year, 12, 5),
        modalidad='PRESENCIAL',
        esta_activo=True
    )
    talleres_list.append(taller_b2b_obj)
    # Talleres B2C Actuales/Futuros
    for i, nombre_int in enumerate(intereses_b2c_list):
        precio_base = precios_base[nombre_int.nombre]
        taller = Taller.objects.create(
            nombre=f'{nombre_int.nombre} Avanzado TMM ({i+1})',
            descripcion=f'Taller avanzado de {nombre_int.nombre} con técnicas complejas.',
            precio=precio_base * Decimal('1.2'),
            cupos_totales=10000,
            categoria=nombre_int,
            modalidad=random.choice(['PRESENCIAL', 'ONLINE']),
            fecha_taller=date(current_year, 12, random.randint(10, 25)),
            esta_activo=True
        )
        talleres_list.append(taller)
    # Talleres B2C Históricos: generar uno por mes desde Junio a Noviembre del año actual
    historical_start_month = 6
    historical_end_month = 11
    for m in range(historical_start_month, historical_end_month + 1):
        # Elegir una categoría aleatoria para el taller histórico
        cat = random.choice(intereses_b2c_list)
        day = random.randint(1, 25)
        try:
            fecha_hist = date(current_year, m, day)
        except Exception:
            # Si el día no existe en el mes (ej. 31), ajustar al último día del mes
            last_day = calendar.monthrange(current_year, m)[1]
            fecha_hist = date(current_year, m, last_day)

        talleres_list.append(Taller.objects.create(
            nombre=f'{cat.nombre} Histórico {fecha_hist.strftime("%b %Y")}',
            precio=precios_base[cat.nombre],
            cupos_totales=20,
            categoria=cat,
            fecha_taller=fecha_hist,
            esta_activo=False,
            cupos_disponibles=0
        ))

    # --- CREAR INSCRIPCIONES HISTÓRICAS PARA LOS TALLERES INACTIVOS (Jun-Nov) ---
    print("6a. Creando inscripciones históricas para talleres inactivos (Jun-Nov)...")
    historical_talleres = [t for t in talleres_list if not t.esta_activo]
    # Clientes B2C disponibles para asignar inscripciones
    clientes_b2c_list = list(Cliente.objects.filter(tipo_cliente='B2C'))
    if clientes_b2c_list and historical_talleres:
        for taller_hist in historical_talleres:
            # Número de inscripciones históricas por taller (3-10)
            num_ins = random.randint(3, min(10, max(3, len(clientes_b2c_list))))
            clientes_seleccionados = random.sample(clientes_b2c_list, min(num_ins, len(clientes_b2c_list)))
            for cliente in clientes_seleccionados:
                try:
                    with transaction.atomic():
                        # Estado aleatorio: la mayoría pagadas, algunas pendientes/abonadas
                        estado = random.choices(['PAGADO', 'PENDIENTE', 'ABONADO'], weights=[0.7, 0.2, 0.1])[0]
                        if estado in ('PAGADO', 'ABONADO'):
                            monto_pago = taller_hist.precio
                        else:
                            monto_pago = Decimal(0)

                        # Fecha entre Junio y Noviembre del año actual
                        start_dt = datetime.datetime.combine(date(current_year, 6, 1), datetime.time.min)
                        end_dt = datetime.datetime.combine(date(current_year, 11, 30), datetime.time.max)
                        fecha_insc = get_random_datetime_between(start_dt, end_dt)

                        Inscripcion.objects.create(
                            cliente=cliente,
                            taller=taller_hist,
                            monto_pagado=monto_pago,
                            estado_pago=estado,
                            fecha_inscripcion=fecha_insc
                        )
                        # Añadir interés relacionado
                        if taller_hist.categoria:
                            cliente.intereses_cliente.add(taller_hist.categoria)
                except IntegrityError:
                    # Evitar duplicados si existen
                    continue
    else:
        print("No hay clientes B2C o talleres históricos para crear inscripciones.")


    # --- 6. INSCRIPCIONES ---
    print("6. Creando Inscripciones...")

    # 6.1. Inscripciones B2B (una por contacto B2B al taller corporativo)
    for cliente_b2b in Cliente.objects.filter(tipo_cliente='B2B'):
        precio_decimal = Decimal(str(taller_b2b_obj.precio))
        try:
             # Creamos la inscripción y descontamos cupo si el taller está activo y tiene cupos
            with transaction.atomic():
                inscripcion = Inscripcion.objects.create(
                    cliente=cliente_b2b,
                    taller=taller_b2b_obj,
                    monto_pagado=precio_decimal, # Asumimos pagado para simplificar
                    estado_pago='PAGADO',
                    fecha_inscripcion=get_random_datetime(30, 90)
                )
                if taller_b2b_obj.esta_activo and taller_b2b_obj.cupos_disponibles > 0:
                     Taller.objects.select_for_update().filter(id=taller_b2b_obj.id).update(
                         cupos_disponibles=F('cupos_disponibles') - 1
                     )
        except IntegrityError:
            print(f"Advertencia: Inscripción duplicada evitada para {cliente_b2b} en {taller_b2b_obj}")
            pass

    # 6.2. Inscripciones B2C (Lógica similar, asegurando variedad)
    clientes_b2c = Cliente.objects.filter(tipo_cliente='B2C')
    talleres_b2c = [t for t in talleres_list if t.categoria != intereses_map['Bienestar Corporativo']]
    inscripciones_creadas = 0

    # Crear ~5 deudores explícitamente
    deudores_count = 0
    for cliente in clientes_b2c[:10]: # Tomar los primeros 10 para intentar hacerlos deudores
        if deudores_count >= 5: break
        taller_activo = random.choice([t for t in talleres_b2c if t.esta_activo])
        if taller_activo.cupos_disponibles > 0:
             monto = Decimal(0)
             estado = 'PENDIENTE'
             if random.random() < 0.5: # 50% de probabilidad de ser abonado
                 monto = taller_activo.precio * Decimal(random.uniform(0.3, 0.6))
                 estado = 'ABONADO'
             try:
                 with transaction.atomic():
                     Inscripcion.objects.create(
                         cliente=cliente, taller=taller_activo, monto_pagado=monto.to_integral_value(),
                         estado_pago=estado, fecha_inscripcion=get_random_datetime(1, 30)
                     )
                     Taller.objects.select_for_update().filter(id=taller_activo.id).update(
                         cupos_disponibles=F('cupos_disponibles') - 1
                     )
                     deudores_count += 1
                     inscripciones_creadas += 1
             except IntegrityError: pass # Evitar duplicados

    # Crear el resto de inscripciones (pagadas o históricas)
    for cliente in clientes_b2c:
        num_inscripciones_cliente = random.randint(0, 2) # Algunos no tendrán inscripciones
        talleres_para_cliente = random.sample(talleres_b2c, min(num_inscripciones_cliente, len(talleres_b2c)))

        for t in talleres_para_cliente:
            estado = 'PAGADO'
            monto = t.precio
            if t.esta_activo:
                fecha_insc = get_random_datetime(1, 60)
            else:
                # Para inscripciones históricas, generar fecha entre Junio y Noviembre del año actual
                start_dt = datetime.datetime.combine(date(current_year, 6, 1), datetime.time.min)
                end_dt = datetime.datetime.combine(date(current_year, 11, 30), datetime.time.max)
                fecha_insc = get_random_datetime_between(start_dt, end_dt)

            try:
                with transaction.atomic():
                    Inscripcion.objects.create(
                        cliente=cliente, taller=t, monto_pagado=monto,
                        estado_pago=estado, fecha_inscripcion=fecha_insc
                    )
                    # Solo descontar cupo si es un taller activo y tiene cupos
                    if t.esta_activo and t.cupos_disponibles > 0:
                         Taller.objects.select_for_update().filter(id=t.id).update(
                             cupos_disponibles=F('cupos_disponibles') - 1
                         )
                    # Añadir interés relacionado al inscribirse
                    if t.categoria:
                        cliente.intereses_cliente.add(t.categoria)
                    inscripciones_creadas += 1
            except IntegrityError:
                pass # Evitar duplicados

    # --- 7. PRODUCTOS Y VENTAS (Lógica sin cambios) ---
    print("7. Creando Kits y Ventas...")
    kit_resina = Producto.objects.create(nombre='Kit Resina Premium', descripcion='Resina y moldes.', precio_venta=Decimal('15000'), stock_actual=50)
    kit_cuaderno = Producto.objects.create(nombre='Kit Encuadernación', descripcion='Para un cuaderno A5.', precio_venta=Decimal('10000'), stock_actual=30)
    kit_timbres = Producto.objects.create(nombre='Goma y Base Timbres', descripcion='Insumos para crear 5 timbres.', precio_venta=Decimal('8000'), stock_actual=100)
    productos_list = [kit_resina, kit_cuaderno, kit_timbres]

    clientes_compradores = random.sample(list(clientes_b2c), min(20, len(clientes_b2c))) # Tomar 20 o menos si no hay suficientes
    ventas_creadas = 0

    for cliente_venta in clientes_compradores:
        # 60% de las ventas serán históricas (entre Junio y Noviembre del año actual)
        if random.random() < 0.6:
            start_dt = datetime.datetime.combine(date(current_year, 6, 1), datetime.time.min)
            end_dt = datetime.datetime.combine(date(current_year, 11, 30), datetime.time.max)
            fecha_venta_aleatoria = get_random_datetime_between(start_dt, end_dt)
        else:
            fecha_venta_aleatoria = get_random_datetime(1, 365)
        productos_en_venta = random.sample(productos_list, random.randint(1, len(productos_list)))
        monto_total_venta = Decimal(0)

        # Usar transacción para la venta y sus detalles
        try:
            with transaction.atomic():
                venta = VentaProducto.objects.create(
                    cliente=cliente_venta, monto_total=Decimal(0),
                    estado_pago='PAGADO', fecha_venta=fecha_venta_aleatoria
                )
                detalles_para_crear = []
                for producto in productos_en_venta:
                    cantidad = random.randint(1, 2) # Vender 1 o 2 unidades
                    precio = producto.precio_venta

                    # Validar stock antes de añadir al detalle
                    producto_actual = Producto.objects.select_for_update().get(pk=producto.id) # Bloquear producto
                    if producto_actual.stock_actual >= cantidad:
                        detalles_para_crear.append(
                            DetalleVenta(venta=venta, producto=producto, cantidad=cantidad, precio_unitario=precio)
                        )
                        monto_total_venta += cantidad * precio
                        # Restar stock (se hará después de crear detalles)
                        producto_actual.stock_actual = F('stock_actual') - cantidad
                        producto_actual.save(update_fields=['stock_actual'])
                    else:
                        print(f"Advertencia: Stock insuficiente para {producto.nombre} en venta simulada para {cliente_venta}. Omitiendo item.")


                if detalles_para_crear: # Solo si se añadió al menos un producto
                    DetalleVenta.objects.bulk_create(detalles_para_crear)
                    venta.monto_total = monto_total_venta
                    venta.save(update_fields=['monto_total'])
                    ventas_creadas += 1
                else:
                    # Si no se pudo añadir ningún detalle por falta de stock, la venta queda en 0 y podría eliminarse,
                    # pero la dejamos para el ejemplo (o podrías borrarla: venta.delete())
                    print(f"Advertencia: Venta #{venta.id} para {cliente_venta} quedó sin detalles por falta de stock.")


        except Exception as e:
             print(f"Error creando venta para {cliente_venta}: {e}")


    print(f"\n✅ POBLACIÓN DE DATOS EXITOSA.")
    print(f"   - {Empresa.objects.count()} Empresas creadas.")
    print(f"   - {Cliente.objects.count()} Contactos (Clientes) creados.")
    print(f"   - {Taller.objects.count()} Talleres creados.")
    print(f"   - {Inscripcion.objects.count()} Inscripciones creadas.")
    print(f"   - {Producto.objects.count()} Productos creados.")
    print(f"   - {VentaProducto.objects.filter(monto_total__gt=0).count()} Ventas creadas con detalles.")


if __name__ == '__main__':
    # Asegúrate que el script se ejecute en el contexto de Django
    # (ya configurado arriba con django.setup())
    populate_initial_data()