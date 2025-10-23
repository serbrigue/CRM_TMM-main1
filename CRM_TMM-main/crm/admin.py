from django.contrib import admin
from .models import Cliente, Taller, Inscripcion, Interes, Producto, VentaProducto, DetalleVenta 

# --- INLINES ---
class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 1 
    readonly_fields = ('precio_unitario_display',)

    def precio_unitario_display(self, obj):
        return f"${obj.precio_unitario:,.0f}"
    precio_unitario_display.short_description = "Precio (CLP)"

# --- ADMINS ---
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'email', 'telefono', 'fecha_nacimiento', 'tipo_cliente', 'fecha_registro')
    search_fields = ('nombre_completo', 'email', 'telefono')
    
    # CORRECCIÓN CLAVE: Añadir el campo Many-to-Many 'intereses_cliente' al list_filter
    list_filter = ('tipo_cliente', 'comuna_vive', 'intereses_cliente')
    
    readonly_fields = ('fecha_registro',)
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre_completo', 'email', 'telefono', 'fecha_nacimiento', 'comuna_vive')
        }),
        ('Segmentación TMM', {
            'fields': (
                'tipo_cliente', 
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
    list_display = ('cliente', 'taller', 'monto_pagado', 'estado_pago', 'fecha_inscripcion')
    list_filter = ('estado_pago', 'taller__nombre', 'fecha_inscripcion')
    search_fields = ('cliente__nombre_completo', 'taller__nombre')
    raw_id_fields = ('cliente', 'taller')

@admin.register(Interes)
class InteresAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio_venta', 'esta_disponible')
    list_filter = ('esta_disponible',)
    search_fields = ('nombre',)

@admin.register(VentaProducto)
class VentaProductoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'fecha_venta', 'monto_total', 'estado_pago')
    list_filter = ('estado_pago', 'fecha_venta')
    search_fields = ('cliente__nombre_completo',)
    inlines = [DetalleVentaInline] 
    readonly_fields = ('monto_total',)