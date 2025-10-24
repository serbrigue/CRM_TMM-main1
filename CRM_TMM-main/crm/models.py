from django.db import models
from django.db.models import F # Necesario para la actualización atómica
from django.contrib.auth.models import User 
from django.utils import timezone
from datetime import date

# --- MODELO 1: Interes ---
# Nuevo modelo para categorizar los temas que le interesan a un cliente para segmentación.
class Interes(models.Model):
    """
    Categorías de interés de los talleres (ej: Resina, Encuadernación).
    Usado para segmentación de marketing (Requerimiento Should Have).
    """
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Interés")
    descripcion = models.TextField(blank=True, verbose_name="Descripción o Palabras Clave")
    
    class Meta:
        verbose_name_plural = "Intereses"
    
    def __str__(self):
        return self.nombre
    
# --- MODELO 2: Cliente ---
# Representa a los clientes individuales (B2C) y contactos de empresas (B2B).
# crm/models.py (Solo el modelo Cliente)

class Cliente(models.Model):
    """
    Modelo para gestionar la información de los clientes de TMM.
    """
    TIPO_CLIENTE_CHOICES = [
        ('B2C', 'Persona Natural'),
        ('B2B', 'Empresa/Institución'),
    ]
    
    # Información personal básica
    nombre_completo = models.CharField(max_length=150, verbose_name="Nombre Completo")
    email = models.EmailField(unique=True, verbose_name="Correo Electrónico")
    
    # CAMPOS NUEVOS/MODIFICADOS:
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    fecha_nacimiento = models.DateField(blank=True, null=True, verbose_name="Fecha de Nacimiento") # Nuevo campo para fidelización
    
    # Segmentación y fidelización
    comuna_vive = models.CharField(max_length=100, blank=True, null=True, verbose_name="Comuna de Residencia")
    tipo_cliente = models.CharField(max_length=3, choices=TIPO_CLIENTE_CHOICES, default='B2C', verbose_name="Tipo de Cliente")
    intereses_cliente = models.ManyToManyField(Interes, blank=True, related_name='clientes', verbose_name="Intereses del Cliente")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones de Gestión (Seguimiento, etc.)")
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.nombre_completo} ({self.get_tipo_cliente_display()})"

# --- MODELO 3: Taller ---
# Representa la oferta de cursos de TMM.
class Taller(models.Model):
    """
    Representa la oferta de cursos de TMM.
    Incluye imagen y relación con Categoría/Interés.
    """
    MODALIDAD_CHOICES = [
        ('PRESENCIAL', 'Presencial'),
        ('ONLINE', 'Online'),
    ]
    
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre del Taller")
    descripcion = models.TextField(verbose_name="Descripción Detallada")
    
    # Soporte para imágenes
    imagen = models.ImageField(upload_to='talleres/', blank=True, null=True, verbose_name="Imagen del Taller")

    # RELACIÓN CLAVE: Un taller pertenece a una sola Categoría/Interés principal
    categoria = models.ForeignKey(
        Interes, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='talleres', 
        verbose_name="Categoría del Taller"
    )

    fecha_taller = models.DateField(verbose_name="Fecha del Taller")
    hora_taller = models.TimeField(blank=True, null=True, verbose_name="Hora de Inicio")
    modalidad = models.CharField(max_length=15, choices=MODALIDAD_CHOICES, default='PRESENCIAL', verbose_name="Modalidad")
    precio = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Precio (CLP)")
    cupos_totales = models.IntegerField(default=10, verbose_name="Cupos Máximos")
    
    # Campo calculado automáticamente
    cupos_disponibles = models.IntegerField(editable=False, default=0, verbose_name="Cupos Disponibles")
    esta_activo = models.BooleanField(default=True, verbose_name="¿Está activo/visible?")
    
    def save(self, *args, **kwargs):
        """Inicializa los cupos disponibles al total en la creación."""
        if not self.id: 
            self.cupos_disponibles = self.cupos_totales
        super().save(*args, **kwargs)

    def cumpleanios_hoy(self):
        """Devuelve True si el cumpleaños del cliente es hoy."""
        if self.fecha_nacimiento:
            # Compara solo mes y día con la fecha actual en la zona horaria del proyecto
            today = timezone.localdate()
            return (self.fecha_nacimiento.day == today.day and 
                    self.fecha_nacimiento.month == today.month)
        return False    

    def __str__(self):
        return f"{self.nombre} ({self.fecha_taller})"

# --- MODELO 4: Inscripcion ---
# Conecta a los Clientes con los Talleres y maneja el estado del pago.
class Inscripcion(models.Model):
    """
    Modelo que registra la inscripción de un cliente a un taller específico.
    Gestiona el estado del pago y facilita la gestión de deudores (RF Must Have).
    """
    ESTADO_PAGO_CHOICES = [
        ('PENDIENTE', 'Pago Pendiente'), # Clave para la gestión de deudores
        ('PAGADO', 'Pagado Completo'),
        ('ABONADO', 'Abonado'),
        ('ANULADO', 'Anulado'),
    ]
    
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='inscripciones')
    taller = models.ForeignKey(Taller, on_delete=models.CASCADE, related_name='inscripciones')
    
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Monto Pagado")
    estado_pago = models.CharField(max_length=10, choices=ESTADO_PAGO_CHOICES, default='PENDIENTE', verbose_name="Estado de Pago")
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Asegura que un cliente solo pueda inscribirse una vez al mismo taller
        unique_together = ('cliente', 'taller')
        verbose_name_plural = "Inscripciones"
        
    def __str__(self):
        return f"{self.cliente.nombre_completo} inscrito en {self.taller.nombre}"
    

class Producto(models.Model):
    """
    Representa los Kits, insumos o productos personalizados que vende TMM 
    (mencionado en las líneas de trabajo B2C).
    """
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre del Producto/Kit")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    precio_venta = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Precio de Venta (CLP)")
    esta_disponible = models.BooleanField(default=True, verbose_name="¿Está disponible para la venta?")
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True, verbose_name="Imagen del Producto")
    stock_actual = models.IntegerField(default=0, verbose_name="Stock Actual en Bodega")
    class Meta:
        verbose_name_plural = "Productos (Kits)"
        
    def __str__(self):
        return self.nombre

# --- NUEVO MODELO 6: VentaProducto ---
class VentaProducto(models.Model):
    """
    Registra la compra de Kits o insumos por un Cliente, cerrando la trazabilidad.
    """
    ESTADO_PAGO_CHOICES = [
        ('PENDIENTE', 'Pago Pendiente'),
        ('PAGADO', 'Pagado Completo'),
        ('ANULADO', 'Anulado'),
    ]
    
    # Relación con el Cliente (para trazabilidad)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='compras_kits')
    
    # Detalle de la venta
    fecha_venta = models.DateTimeField(auto_now_add=True)
    monto_total = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Monto Total Pagado")
    estado_pago = models.CharField(max_length=10, choices=ESTADO_PAGO_CHOICES, default='PAGADO', verbose_name="Estado de Pago")
    
    class Meta:
        verbose_name_plural = "Ventas de Productos"
        
    def __str__(self):
        return f"Venta de Kit #{self.id} a {self.cliente.nombre_completo}"

# --- NUEVO MODELO 7: DetalleVenta ---
class DetalleVenta(models.Model):
    """
    Detalle de los productos incluidos en cada VentaProducto (muchos productos en una venta).
    """
    venta = models.ForeignKey(VentaProducto, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT) # Protege el producto si está vendido
    cantidad = models.IntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Precio al Vender")

    class Meta:
        verbose_name_plural = "Detalles de Venta"
        
    def subtotal(self):
        return self.cantidad * self.precio_unitario