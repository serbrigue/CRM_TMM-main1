from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('talleres/', views.catalogo_talleres, name='catalogo_talleres'),
    path('talleres/<int:taller_id>/', views.detalle_taller_inscripcion, name='detalle_taller'), 
    path('pago/<int:inscripcion_id>/', views.pago_simulado, name='pago_simulado'),
    path('gestion/deudores/', views.gestion_deudores, name='gestion_deudores'),
    path('gestion/email/preview/', views.email_preview, name='email_preview'),
    path('gestion/reportes/', views.panel_reportes, name='panel_reportes'),
    path('cuenta/registro/', views.registro_cliente, name='registro_cliente'),
    path('gestion/clientes/', views.listado_clientes, name='listado_clientes'),
    path('gestion/clientes/<int:cliente_id>/', views.detalle_cliente_admin, name='detalle_cliente_admin'),
    path('productos/', views.catalogo_productos, name='catalogo_productos'),
    path('productos/<int:producto_id>/', views.detalle_producto, name='detalle_producto'),
    path('cuenta/perfil/', views.perfil_usuario, name='perfil_usuario'),
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/add/<int:producto_id>/', views.agregar_a_carrito, name='agregar_a_carrito'),
    path('carrito/update/', views.actualizar_carrito, name='actualizar_carrito'),
    path('carrito/checkout/', views.finalizar_compra, name='finalizar_compra'),
    path('logout/', views.logout, name='logout'),
]