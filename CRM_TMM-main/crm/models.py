# crm/models.py
from django.db import models
from django.db.models import F # Necesario para la actualización atómica
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date

# --- MODELO NUEVO: Empresa ---
class Empresa(models.Model):
    """
    Representa a una empresa o institución cliente (B2B).
    """
    razon_social = models.CharField(max_length=200, unique=True, verbose_name="Razón Social")
    rut = models.CharField(max_length=12, blank=True, null=True, unique=True, verbose_name="RUT") # Opcional y único si se ingresa
    direccion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
    telefono_empresa = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono Empresa")
    # Podrías añadir más campos como 'rubro', 'sitio_web', etc.
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Empresa (B2B)"
        verbose_name_plural = "Empresas (B2B)"

    def __str__(self):
        return self.razon_social


# --- MODELO 1: Interes (Sin cambios) ---
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

# --- MODELO 2: Cliente (MODIFICADO) ---
# Se añade ForeignKey a Empresa y se ajustan comentarios/etiquetas
class Cliente(models.Model):
    """
    Modelo para gestionar la información de los contactos de TMM.
    Puede ser una persona natural (B2C) o un contacto de una Empresa (B2B).
    """
    TIPO_CLIENTE_CHOICES = [
        ('B2C', 'Persona Natural'),
        ('B2B', 'Contacto Empresa'), # Etiqueta actualizada
    ]

    # Información básica del contacto
    nombre_completo = models.CharField(max_length=150, verbose_name="Nombre Completo (Contacto)") # Etiqueta actualizada
    email = models.EmailField(unique=True, verbose_name="Correo Electrónico (Contacto)") # Etiqueta actualizada
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono (Contacto)") # Etiqueta actualizada
    fecha_nacimiento = models.DateField(blank=True, null=True, verbose_name="Fecha de Nacimiento (si aplica)") # Etiqueta actualizada

    # --- NUEVO CAMPO: Vínculo con Empresa ---
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL, # Si se borra la empresa, el contacto no se borra, solo pierde el vínculo
        blank=True,
        null=True,
        related_name='contactos', # Permite acceder a los contactos desde una empresa: empresa.contactos.all()
        verbose_name="Empresa (si aplica)"
    )
    # --- FIN NUEVO CAMPO ---

    # Segmentación y fidelización (se mantiene)
    comuna_vive = models.CharField(max_length=100, blank=True, null=True, verbose_name="Comuna de Residencia")
    tipo_cliente = models.CharField(max_length=3, choices=TIPO_CLIENTE_CHOICES, default='B2C', verbose_name="Tipo de Contacto") # Etiqueta actualizada
    intereses_cliente = models.ManyToManyField(Interes, blank=True, related_name='clientes', verbose_name="Intereses del Contacto") # Etiqueta actualizada
    observaciones = models.TextField(blank=True, verbose_name="Observaciones de Gestión (Seguimiento, etc.)")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.tipo_cliente == 'B2B' and self.empresa:
            return f"{self.nombre_completo} ({self.empresa.razon_social})"
        return f"{self.nombre_completo} ({self.get_tipo_cliente_display()})"

# --- MODELO 3: Taller (Sin cambios) ---
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
    imagen = models.ImageField(upload_to='talleres/', blank=True, null=True, verbose_name="Imagen del Taller")
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
    cupos_disponibles = models.IntegerField(editable=False, default=0, verbose_name="Cupos Disponibles")
    esta_activo = models.BooleanField(default=True, verbose_name="¿Está activo/visible?")

    def save(self, *args, **kwargs):
        """Inicializa los cupos disponibles al total en la creación."""
        if not self.id:
            self.cupos_disponibles = self.cupos_totales
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} ({self.fecha_taller})"

# --- MODELO 4: Inscripcion (Sin cambios) ---
class Inscripcion(models.Model):
    """
    Modelo que registra la inscripción de un cliente a un taller específico.
    Gestiona el estado del pago y facilita la gestión de deudores (RF Must Have).
    """
    ESTADO_PAGO_CHOICES = [
        ('PENDIENTE', 'Pago Pendiente'),
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
        unique_together = ('cliente', 'taller')
        verbose_name_plural = "Inscripciones"

    def __str__(self):
        return f"{self.cliente.nombre_completo} inscrito en {self.taller.nombre}"


# --- MODELO 5: Producto (Sin cambios) ---
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

# --- MODELO 6: VentaProducto (Sin cambios) ---
class VentaProducto(models.Model):
    """
    Registra la compra de Kits o insumos por un Cliente, cerrando la trazabilidad.
    """
    ESTADO_PAGO_CHOICES = [
        ('PENDIENTE', 'Pago Pendiente'),
        ('PAGADO', 'Pagado Completo'),
        ('ANULADO', 'Anulado'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='compras_kits')
    fecha_venta = models.DateTimeField(auto_now_add=True)
    monto_total = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Monto Total Pagado")
    estado_pago = models.CharField(max_length=10, choices=ESTADO_PAGO_CHOICES, default='PAGADO', verbose_name="Estado de Pago")

    class Meta:
        verbose_name_plural = "Ventas de Productos"

    def __str__(self):
        return f"Venta de Kit #{self.id} a {self.cliente.nombre_completo}"

# --- MODELO 7: DetalleVenta (Sin cambios) ---
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


# --- MODELO 8: EmailLog (Registra intentos de envío de correo) ---
class EmailLog(models.Model):
    """Registra intentos de envío de correos desde el sistema para trazabilidad.

    Guarda destinatario, asunto, cuerpo (texto), cuerpo HTML opcional,
    estado (SUCCESS/FAIL), mensaje de error y la inscripción relacionada si aplica.
    """
    STATUS_CHOICES = [
        ('SUCCESS', 'Enviado'),
        ('FAIL', 'Fallido'),
    ]

    recipient = models.EmailField(blank=True, null=True)
    subject = models.CharField(max_length=255)
    body_text = models.TextField(blank=True, null=True)
    body_html = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SUCCESS')
    error_message = models.TextField(blank=True, null=True)
    inscripcion = models.ForeignKey('Inscripcion', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Email to {self.recipient} [{self.status}] at {self.created_at}"