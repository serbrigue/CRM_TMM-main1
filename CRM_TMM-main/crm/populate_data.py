# crm/populate_data.py
import os
import django
import datetime
import random
from decimal import Decimal
from django.db.utils import IntegrityError
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import F

# Importar tus modelos
from crm.models import Interes, Cliente, Taller, Inscripcion, Producto, VentaProducto, DetalleVenta 

# --- VARIABLES DE AYUDA Y NOMBRES ---
NOMBRES_FEMENINOS = ["Jessica", "Pamela", "Angélica", "Daniela", "Cynthia", "Marisol", "Nataly", "Fernanda", "Sara", "Gloria", "Carla", "Maleni", "Noemi", "Rosa"]
APELLIDOS = ["Vargas", "López", "Gómez", "Díaz", "Escobar", "Ibaeta", "Barrera", "González", "Sánchez", "Muñoz"]
COMUNAS = ["Valparaíso", "Viña del Mar", "Quilpué", "Villa Alemana"]
CANALES = ['INSTAGRAM', 'WHATSAPP', 'FACEBOOK', 'RECOMENDACION'] 

# --- FUNCIONES DE AYUDA ---

def get_random_date(start_year, end_year):
    """Genera una fecha de nacimiento aleatoria entre dos años."""
    start_date = datetime.date(start_year, 1, 1)
    end_date = datetime.date(end_year, 12, 31)
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    return start_date + datetime.timedelta(days=random_number_of_days)

def get_random_datetime(days_ago_min, days_ago_max):
    """Genera un datetime aleatorio en el pasado."""
    start_time = timezone.now() - datetime.timedelta(days=days_ago_max)
    end_time = timezone.now() - datetime.timedelta(days=days_ago_min)
    time_diff = end_time - start_time
    random_seconds = random.randrange(int(time_diff.total_seconds()))
    return start_time + datetime.timedelta(seconds=random_seconds)

def clean_database():
    """Elimina todos los datos de los modelos de prueba para empezar limpio."""
    print("Limpiando la base de datos...")
    DetalleVenta.objects.all().delete()
    VentaProducto.objects.all().delete()
    Producto.objects.all().delete()
    Inscripcion.objects.all().delete()
    Taller.objects.all().delete()
    Cliente.objects.all().delete()
    Interes.objects.all().delete()
    User.objects.filter(username__startswith='cliente_').delete()
    User.objects.filter(username='admin_tmm').delete()
    
def populate_initial_data():
    """Crea los datos de prueba amplios (40 Clientes, 5+ Talleres, 40+ Inscripciones)."""
    
    clean_database()
    print("Iniciando población de datos ampliada...")
    
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
        intereses_map[nombre] = Interes.objects.create(nombre=nombre, descripcion=f"Interés principal en {nombre}.")
        precios_base[nombre] = Decimal(precio_base) 
    
    intereses_b2c_list = [intereses_map[n] for n in intereses_map if n != 'Bienestar Corporativo'] 

    # --- 2. SUPERUSUARIO ---
    print("2. Creando Superusuario...")
    if not User.objects.filter(username='admin_tmm').exists():
        User.objects.create_superuser('admin_tmm', 'carolina@tmm.cl', 'adminpass')

    # --- 3. CLIENTES (40 Clientes: 37 B2C, 3 B2B) ---
    print("3. Creando 40 Clientes y Usuarios...")
    clientes_list = []
    
    # 3.1. Clientes B2C (37)
    for i in range(1, 38):
        nombre = random.choice(NOMBRES_FEMENINOS)
        apellido = random.choice(APELLIDOS)
        email = f'cliente_{i}_{random.randint(100,999)}@testmail.com'
        telefono = f'+569{random.randint(10000000, 99999999)}'
        username = f'cliente_{i}'
        
        try:
            user = User.objects.create_user(username, email, 'password123', first_name=nombre, last_name=apellido)
        except IntegrityError: 
            email = f'cliente_{i}_{random.randint(100,999)}@testmail{random.randint(1,99)}.com'
            user = User.objects.create_user(username, email, 'password123', first_name=nombre, last_name=apellido)

        cliente = Cliente.objects.create(
            nombre_completo=f'{nombre} {apellido}',
            email=email,
            telefono=telefono,
            fecha_nacimiento=get_random_date(1985, 2000),
            comuna_vive=random.choice(COMUNAS),
            tipo_cliente='B2C',
            observaciones=f"Cliente de prueba B2C #{i}. Contactado por {random.choice(CANALES)}."
        )
        cliente.intereses_cliente.set(random.sample(intereses_b2c_list, random.randint(1, 2)))
        clientes_list.append(cliente)

    # 3.2. Clientes B2B (3)
    for i in range(1, 4):
        nombre_empresa = f"Empresa/Inst. #{i} RRHH"
        email_empresa = f'b2b_{i}@empresa-fake.cl'
        cliente = Cliente.objects.create(
            nombre_completo=nombre_empresa,
            email=email_empresa,
            telefono=f'+562{random.randint(10000000, 99999999)}',
            comuna_vive=random.choice(["Santiago", "Valparaíso"]),
            tipo_cliente='B2B',
            observaciones="Contacto para propuesta anual de bienestar corporativo."
        )
        cliente.intereses_cliente.add(intereses_map['Bienestar Corporativo'])
        clientes_list.append(cliente)

    # --- 4. TALLERES (7 Talleres - 5 Principales + 2 Históricos) ---
    print("4. Creando 7 Talleres (5 Principales, 2 Históricos)...")
    talleres_list = []
    
    # Taller B2B (1)
    precio_b2b = precios_base['Bienestar Corporativo']
    taller_b2b_obj = Taller.objects.create( 
        nombre='Taller Autocuidado Corporativo', 
        descripcion='Sesión de manualidades y bienestar para equipos.', 
        precio=precio_b2b, 
        cupos_totales=30, 
        categoria=intereses_map['Bienestar Corporativo'], 
        fecha_taller=datetime.date(2025, 12, 5),
        esta_activo=True
    )
    talleres_list.append(taller_b2b_obj)

    # Talleres B2C Actuales/Futuros (4)
    for i, nombre_int in enumerate([n for n in intereses_map if n != 'Bienestar Corporativo']):
        precio_base = precios_base[nombre_int]
        taller = Taller.objects.create(
            nombre=f'{nombre_int} Avanzado TMM', 
            descripcion=f'Taller avanzado de {nombre_int} con técnicas complejas.', 
            precio=precio_base * Decimal('1.2'), 
            cupos_totales=random.choice([10, 12, 15]), 
            categoria=intereses_map[nombre_int], 
            modalidad=random.choice(['PRESENCIAL', 'ONLINE']),
            fecha_taller=datetime.date(2025, 12, random.randint(10, 25)),
            esta_activo=True
        )
        talleres_list.append(taller)
        
    # Talleres B2C Históricos (2 - populares para la gráfica de clientes)
    precio_resina_hist = precios_base['Resina']
    precio_encuad_hist = precios_base['Encuadernación']
    
    talleres_list.append(Taller.objects.create(nombre='Resina Inicial (Oct)', precio=precio_resina_hist, cupos_totales=20, categoria=intereses_map['Resina'], fecha_taller=datetime.date(2025, 10, 10), esta_activo=False, cupos_disponibles=0))
    talleres_list.append(Taller.objects.create(nombre='Encuadernación Básica (Sep)', precio=precio_encuad_hist, cupos_totales=20, categoria=intereses_map['Encuadernación'], fecha_taller=datetime.date(2025, 9, 20), esta_activo=False, cupos_disponibles=0))

    # --- 5. INSCRIPCIONES (60 Registros, simula 40 clientes únicos) ---
    print("5. Creando más de 40 Inscripciones (incluye repetidos) y Deudores...")
    
    # 5.1. Clientes B2B: Inscriben al taller corporativo
    taller_b2b = talleres_list[0]
    for cliente_b2b in clientes_list[-3:]:
        precio_decimal = Decimal(str(taller_b2b.precio)) 
        Inscripcion.objects.create(cliente=cliente_b2b, taller=taller_b2b, monto_pagado=precio_decimal, estado_pago='PAGADO', fecha_inscripcion=get_random_datetime(30, 90))
        Taller.objects.filter(id=taller_b2b.id).update(cupos_disponibles=F('cupos_disponibles') - 1)


    # 5.2. Clientes B2C: 
    # 5.2.1. 5 Deudores (PENDIENTE/ABONADO en un taller futuro)
    clientes_deudores = clientes_list[3:8] 
    for cliente_deudor in clientes_deudores:
        taller_activo = random.choice([t for t in talleres_list if t.esta_activo and t.categoria.nombre != 'Bienestar Corporativo'])
        
        monto = Decimal(0)
        estado = 'PENDIENTE'
        precio_decimal = Decimal(str(taller_activo.precio)) 
        
        if random.choice([True, False]):
             monto = precio_decimal * Decimal('0.3') 
             estado = 'ABONADO'
             
        Inscripcion.objects.create(cliente=cliente_deudor, taller=taller_activo, monto_pagado=monto, estado_pago=estado, fecha_inscripcion=get_random_datetime(1, 15))
        Taller.objects.filter(id=taller_activo.id).update(cupos_disponibles=F('cupos_disponibles') - 1)

    # 5.2.2. 32 Clientes B2C restantes con 1-3 inscripciones pagadas/abonadas
    clientes_restantes = clientes_list[:3] + clientes_list[8:] 
    
    for cliente in clientes_restantes:
        num_inscripciones = random.randint(1, 3) 
        talleres_cliente = random.sample(talleres_list, min(num_inscripciones, len(talleres_list)))
        
        for t in talleres_cliente:
            precio_decimal = Decimal(str(t.precio)) 
            
            if t.esta_activo: 
                # Inscripciones recientes (últimos 3 meses) para talleres activos
                monto = precio_decimal * random.choice([Decimal(1), Decimal('0.5')]) 
                estado = 'PAGADO' if monto == precio_decimal else 'ABONADO'
                fecha_insc = get_random_datetime(1, 90) # <-- 3 meses
                
            else: 
                # Inscripciones históricas (últimos 18 meses) para talleres pasados
                monto = precio_decimal
                estado = 'PAGADO'
                fecha_insc = get_random_datetime(90, 540) # <-- 3 meses a 18 meses
            
            try:
                Inscripcion.objects.create(
                    cliente=cliente, 
                    taller=t, 
                    monto_pagado=monto, 
                    estado_pago=estado, 
                    fecha_inscripcion=fecha_insc
                )
                cliente.intereses_cliente.add(t.categoria)
                if t.esta_activo and t.cupos_disponibles > 0:
                    Taller.objects.filter(id=t.id).update(cupos_disponibles=F('cupos_disponibles') - 1)
            except IntegrityError:
                pass 
    

    # --- 6. PRODUCTOS Y VENTAS (20 Ventas) ---
    print("6. Creando Kits y 20 Ventas (Trazabilidad)...")
    
    kit_resina = Producto.objects.create(nombre='Kit Resina Premium', descripcion='Resina y moldes.', precio_venta=Decimal('15000'))
    kit_cuaderno = Producto.objects.create(nombre='Kit Encuadernación', descripcion='Para un cuaderno A5.', precio_venta=Decimal('10000'))
    kit_timbres = Producto.objects.create(nombre='Goma y Base Timbres', descripcion='Insumos para crear 5 timbres.', precio_venta=Decimal('8000'))
    productos_list = [kit_resina, kit_cuaderno, kit_timbres]
    
    clientes_b2c = [c for c in clientes_list if c.tipo_cliente == 'B2C']
    clientes_compradores = random.sample(clientes_b2c, 20)
    
    for cliente_venta in clientes_compradores:
        
        # Ventas distribuidas en los últimos 12 meses (365 días)
        fecha_venta_aleatoria = get_random_datetime(1, 365) 
        
        venta = VentaProducto.objects.create(cliente=cliente_venta, monto_total=Decimal(0), estado_pago='PAGADO', fecha_venta=fecha_venta_aleatoria)
        monto_total_venta = Decimal(0)
        
        productos_en_venta = random.sample(productos_list, random.randint(1, len(productos_list))) 
        
        for producto in productos_en_venta:
            cantidad = random.randint(1, 3)
            precio = producto.precio_venta 
            
            DetalleVenta.objects.create(venta=venta, producto=producto, cantidad=cantidad, precio_unitario=precio)
            monto_total_venta += cantidad * precio
        
        venta.monto_total = monto_total_venta
        venta.save()

    print(f"\n✅ POBLACIÓN DE DATOS EXITOSA. {Cliente.objects.count()} clientes, {Taller.objects.count()} talleres, {Inscripcion.objects.count()} inscripciones y {VentaProducto.objects.count()} ventas creadas.")


if __name__ == '__main__':
    populate_initial_data()