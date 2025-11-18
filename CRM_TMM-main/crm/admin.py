# crm/admin.py
from django.contrib import admin
from .models import Cliente, Taller, Inscripcion, Interes, Producto, VentaProducto, DetalleVenta, Empresa # Importar Empresa

# --- INLINES (Sin cambios) ---
class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 1
    readonly_fields = ('precio_unitario_display',)

    def precio_unitario_display(self, obj):
        # Corrección: Asegurar que obj.precio_unitario no sea None antes de formatear
        return f"${obj.precio_unitario:,.0f}" if obj.precio_unitario is not None else "$0"
    precio_unitario_display.short_description = "Precio (CLP)"

# --- ADMINS ---

# --- NUEVO: Admin para Empresa ---
@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'rut', 'telefono_empresa', 'fecha_registro')
    search_fields = ('razon_social', 'rut')
    list_filter = ('fecha_registro',)
    readonly_fields = ('fecha_registro',)
    # Podríamos añadir un Inline para ver los contactos directamente aquí
    # inlines = [ClienteInline] # (Requeriría definir ClienteInline)

# --- MODIFICADO: Admin para Cliente ---
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'email', 'telefono', 'empresa', 'tipo_cliente', 'fecha_registro') # Añadido 'empresa'
    search_fields = ('nombre_completo', 'email', 'telefono', 'empresa__razon_social') # Añadido búsqueda por empresa
    list_filter = ('tipo_cliente', 'comuna_vive', 'intereses_cliente', 'empresa') # Añadido filtro por empresa
    readonly_fields = ('fecha_registro',)
    # Usar raw_id_fields para el campo 'empresa' si hay muchas empresas, para mejor rendimiento
    raw_id_fields = ('empresa',)

    fieldsets = (
        ('Información del Contacto', { # Título actualizado
            'fields': ('nombre_completo', 'email', 'telefono', 'fecha_nacimiento', 'comuna_vive')
        }),
        # --- NUEVO: Sección Empresa ---
         ('Información B2B (Opcional)', {
            'classes': ('collapse',), # Opcional: para que esté colapsado por defecto
            'fields': ('empresa',),
        }),
        # --- FIN NUEVO ---
        ('Segmentación TMM', {
            'fields': (
                'tipo_cliente', # Asegurarse que este campo se edite para marcar si es B2B
                'intereses_cliente',
                'observaciones'
            )
        }),
    )


@admin.register(Taller)
class TallerAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'fecha_taller', 'modalidad', 'precio', 'cupos_disponibles', 'esta_activo')
    list_filter = ('modalidad', 'categoria', 'esta_activo', 'fecha_taller')
    search_fields = ('nombre', 'descripcion')
    readonly_fields = ('cupos_disponibles',)

@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ('get_cliente_display', 'taller', 'monto_pagado', 'estado_pago', 'fecha_inscripcion') # Método para mostrar nombre/empresa
    list_filter = ('estado_pago', 'taller__nombre', 'fecha_inscripcion', 'cliente__tipo_cliente') # Añadido filtro por tipo cliente
    search_fields = ('cliente__nombre_completo', 'taller__nombre', 'cliente__empresa__razon_social') # Añadido búsqueda por empresa
    raw_id_fields = ('cliente', 'taller')

    # Método para mejorar la visualización del cliente en el listado
    @admin.display(description='Cliente / Empresa', ordering='cliente__nombre_completo')
    def get_cliente_display(self, obj):
        if obj.cliente.tipo_cliente == 'B2B' and obj.cliente.empresa:
            return f"{obj.cliente.nombre_completo} ({obj.cliente.empresa.razon_social})"
        return obj.cliente.nombre_completo


@admin.register(Interes)
class InteresAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio_venta', 'stock_actual', 'esta_disponible') # Añadido stock
    list_filter = ('esta_disponible',)
    search_fields = ('nombre',)
    readonly_fields = () # Quitar stock si quieres editarlo aquí

@admin.register(VentaProducto)
class VentaProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_cliente_venta_display', 'fecha_venta', 'monto_total', 'estado_pago') # Mejorar display cliente
    list_filter = ('estado_pago', 'fecha_venta', 'cliente__tipo_cliente') # Añadir filtro tipo cliente
    search_fields = ('cliente__nombre_completo', 'cliente__empresa__razon_social') # Añadir búsqueda empresa
    inlines = [DetalleVentaInline]
    readonly_fields = ('monto_total',)
    raw_id_fields = ('cliente',) # Recomendado si hay muchos clientes

    @admin.display(description='Cliente / Empresa', ordering='cliente__nombre_completo')
    def get_cliente_venta_display(self, obj):
        # Mostrar nombre y empresa si es B2B
        if obj.cliente and getattr(obj.cliente, 'tipo_cliente', None) == 'B2B' and getattr(obj.cliente, 'empresa', None):
            return f"{obj.cliente.nombre_completo} ({obj.cliente.empresa.razon_social})"
        return getattr(obj.cliente, 'nombre_completo', '')

