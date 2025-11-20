# crm/tests/test_web.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date
from crm.models import Taller, Interes, Cliente, Inscripcion, Producto, VentaProducto
from crm.forms import RegistroClienteForm

# ====================================================================
# CONFIGURACIÓN BASE Y DATOS DE PRUEBA
# ====================================================================

class TestSetup(TestCase):
    """Clase base para configurar datos comunes a varios tests."""

    def setUp(self):
        # 1. Crear un interés (categoría) para talleres
        self.interes_resina = Interes.objects.create(nombre='Resina', descripcion='Interés en resina')
        self.interes_encuadernacion = Interes.objects.create(nombre='Encuadernación', descripcion='Interés en encuadernación')

        # 2. Crear un taller activo (con cupos)
        self.taller_activo = Taller.objects.create(
            nombre='Taller de Resina Activo',
            descripcion='Taller de prueba activo.',
            precio=Decimal('10000'),
            cupos_totales=2,
            categoria=self.interes_resina,
            fecha_taller=date(2099, 12, 1),
            esta_activo=True
        )

        # 3. Crear un producto para el carrito
        self.producto_kit = Producto.objects.create(
            nombre='Kit Resina Básica',
            descripcion='Kit de prueba',
            precio_venta=Decimal('5000'),
            stock_actual=10,
            esta_disponible=True
        )

        # 4. Crear un usuario y cliente autenticado (para pruebas de acceso)
        self.user_auth = User.objects.create_user(
            username='testuser', email='test@test.com', password='password123',
            first_name='Usuario', last_name='Prueba'
        )
        self.cliente_auth = Cliente.objects.create(
            nombre_completo='Usuario Prueba',
            email=self.user_auth.email,
            tipo_cliente='B2C'
        )
        self.client_auth_session = Client()
        self.client_auth_session.login(username='testuser', password='password123')

        # 5. Crear un superusuario (para pruebas de vistas administrativas)
        self.superuser = User.objects.create_superuser(
            username='admin_test', email='admin@test.com', password='adminpass'
        )
        self.client_admin_session = Client()
        self.client_admin_session.login(username='admin_test', password='adminpass')

# ====================================================================
# PRUEBAS DE VISTAS PÚBLICAS
# ====================================================================

class PublicViewTests(TestSetup):

    def test_home_view_loads(self):
        """Asegura que la página de inicio carga y usa el template correcto."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'crm/home.html')

    def test_catalogo_talleres_shows_active_taller(self):
        """Asegura que solo los talleres activos son visibles en el catálogo."""
        # Crear un taller inactivo
        Taller.objects.create(
            nombre='Taller Inactivo', precio=Decimal('5000'), cupos_totales=5,
            categoria=self.interes_resina, fecha_taller=date(2025, 1, 1), esta_activo=False,
            descripcion='Test'
        )
        response = self.client.get(reverse('catalogo_talleres'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['talleres']), 1)
        self.assertEqual(response.context['talleres'][0], self.taller_activo)

# ====================================================================
# PRUEBAS DE REGISTRO DE CLIENTES
# ====================================================================

class RegistrationTests(TestCase):

    def test_registro_cliente_view_success(self):
        """Prueba el flujo completo de registro de cliente exitoso."""
        url = reverse('registro_cliente')
        data = {
            'username': 'newuser',
            'email': 'new@client.com',
            'first_name': 'New',
            'last_name': 'Client',
            'password1': 'SecurePass123',
            'password2': 'SecurePass123',
            'telefono': '+56912345678',
            'fecha_nacimiento': '1990-10-20',
        }
        response = self.client.post(url, data, follow=True)
        
        # 1. Verifica la redirección a 'home' después del login automático
        self.assertEqual(response.status_code, 200) 
        self.assertTemplateUsed(response, 'crm/home.html')
        
        # 2. Verifica la creación de User y Cliente
        self.assertTrue(User.objects.filter(username='newuser').exists())
        self.assertTrue(Cliente.objects.filter(email='new@client.com').exists())
        
        # 3. Verifica que los datos extras se guardaron en Cliente
        cliente = Cliente.objects.get(email='new@client.com')
        self.assertEqual(cliente.nombre_completo, 'New Client') # El método save del form genera el nombre completo
        self.assertEqual(cliente.telefono, '+56912345678')
        self.assertEqual(str(cliente.fecha_nacimiento), '1990-10-20')

    def test_registro_cliente_form_email_exists(self):
        """Prueba la validación de email duplicado en RegistroClienteForm."""
        User.objects.create_user(username='existing', email='duplicate@test.com', password='p')
        
        form_data = {
            'username': 'anotheruser',
            'email': 'duplicate@test.com', # Email duplicado
            'first_name': 'A',
            'last_name': 'B',
            'password_1': 'SecurePass123',
            'password_2': 'SecurePass123',
        }
        
        form = RegistroClienteForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('Este correo electrónico ya está registrado.', form.errors['email'])


# ====================================================================
# PRUEBAS DE ACCESO Y PERFIL DE USUARIO
# ====================================================================

class AuthRequiredTests(TestSetup):

    def test_perfil_usuario_unauthenticated_redirects(self):
        """Asegura que el perfil de usuario requiere autenticación."""
        response = self.client.get(reverse('perfil_usuario'))
        self.assertEqual(response.status_code, 302)
        # Verifica que redirige a la URL de login
        self.assertIn(reverse('login'), response.url) 

    def test_perfil_usuario_authenticated_loads(self):
        """Asegura que el perfil de usuario autenticado carga correctamente."""
        response = self.client_auth_session.get(reverse('perfil_usuario'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'crm/profile.html')
        # El contexto 'cliente' debería ser el objeto Cliente asociado al usuario autenticado
        self.assertEqual(response.context['cliente'], self.cliente_auth)

    def test_gestion_deudores_unauthenticated_redirects(self):
        """Asegura que la vista administrativa requiere autenticación."""
        response = self.client.get(reverse('gestion_deudores'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_gestion_deudores_normal_user_denied(self):
        """Asegura que un usuario normal es denegado en vista administrativa."""
        response = self.client_auth_session.get(reverse('gestion_deudores'))
        # user_passes_test por defecto retorna 403 Forbidden o redirige (si no hay login)
        # Dado que está autenticado, debería obtener un 403 o redirigir con un error
        self.assertIn(response.status_code, (302, 403)) 
        
    def test_gestion_deudores_superuser_access(self):
        """Asegura que un superusuario puede acceder a la vista administrativa."""
        response = self.client_admin_session.get(reverse('gestion_deudores'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'crm/gestion_deudores.html')


# ====================================================================
# PRUEBAS DE LÓGICA DE NEGOCIO (INSCRIPCIÓN y CARRITO)
# ====================================================================

class EnrollmentLogicTests(TestSetup):

    def test_anonymous_enrollment_via_web_success(self):
        """Prueba la inscripción anónima enviando un POST al detalle del taller."""
        url = reverse('detalle_taller', args=[self.taller_activo.id])
        data = {
            'nombre': 'Ana Anonima', 
            'email': 'ana.anonima@test.com', 
            'telefono': '+56912345678'
        }
        
        # Simular la solicitud POST
        response = self.client.post(url, data, follow=True)
        
        # 1. Debe redirigir a la página de pago simulado
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'crm/pago_simulado.html')
        
        # 2. Verifica la creación de Inscripción y Cliente
        self.assertTrue(Cliente.objects.filter(email='ana.anonima@test.com').exists())
        cliente = Cliente.objects.get(email='ana.anonima@test.com')
        self.assertTrue(Inscripcion.objects.filter(cliente=cliente, taller=self.taller_activo).exists())
        
        # 3. Verifica la actualización de cupos
        self.taller_activo.refresh_from_db()
        self.assertEqual(self.taller_activo.cupos_disponibles, 1) # Originalmente 2 - 1 = 1

    def test_add_to_cart_and_checkout_success(self):
        """Prueba el flujo de agregar al carrito y finalizar la compra."""
        
        # 1. Añadir el producto al carrito (simula clic en el botón)
        add_url = reverse('agregar_a_carrito', args=[self.producto_kit.id])
        # La vista redirige a 'ver_carrito'
        response_add = self.client_auth_session.post(add_url, follow=True)
        
        # 2. Verificar el carrito (debe estar en la sesión)
        self.assertIn(str(self.producto_kit.id), self.client_auth_session.session['carrito'])
        
        # 3. Finalizar la compra
        checkout_url = reverse('finalizar_compra')
        response_checkout = self.client_auth_session.post(checkout_url, follow=True)
        
        # 4. Verificar la redirección a 'home' después de la compra
        self.assertEqual(response_checkout.status_code, 200)
        self.assertTemplateUsed(response_checkout, 'crm/home.html')
        
        # 5. Verificar la creación de VentaProducto
        self.assertTrue(VentaProducto.objects.filter(cliente=self.cliente_auth, estado_pago='PAGADO').exists())
        venta = VentaProducto.objects.get(cliente=self.cliente_auth)
        self.assertEqual(venta.monto_total, self.producto_kit.precio_venta)
        
        # 6. Verificar que el stock se descontó
        self.producto_kit.refresh_from_db()
        self.assertEqual(self.producto_kit.stock_actual, 9) # Originalmente 10 - 1 = 9