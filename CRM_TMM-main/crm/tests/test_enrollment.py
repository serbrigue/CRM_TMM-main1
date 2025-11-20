# crm/tests/test_enrollment.py
from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
from crm.models import Taller, Interes, Cliente, Inscripcion
from datetime import date


class EnrollmentTests(TestCase):

    def setUp(self):
        # Crear interés y taller
        self.interes = Interes.objects.create(nombre='Test', descripcion='desc')
        self.taller = Taller.objects.create(
            nombre='Taller Test', descripcion='desc', precio=Decimal('10000'),
            cupos_totales=2, categoria=self.interes, fecha_taller=date(2099, 12, 1), esta_activo=True
        )
        # Se corrige la URL de la API a la vista web real
        self.enroll_url = reverse('detalle_taller', args=[self.taller.id])
        self.client_anonymous = Client()

    def test_anonymous_enrollment_success(self):
        """Prueba que la inscripción anónima sea exitosa y redirija al pago simulado (302)."""
        data = {'nombre': 'Ana', 'email': 'ana@test.com', 'telefono': '+56912345678'}
        
        # La vista de inscripción redirige (302) al checkout después de crear la inscripción
        response = self.client_anonymous.post(self.enroll_url, data)
        
        # 1. Verificación del estado de redirección
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('pago_simulado', args=[1]))) 
        
        # 2. Verificación de la lógica
        self.assertEqual(Inscripcion.objects.count(), 1)
        self.taller.refresh_from_db()
        self.assertEqual(self.taller.cupos_disponibles, self.taller.cupos_totales - 1)
        cliente = Cliente.objects.get(email='ana@test.com')
        self.assertEqual(cliente.telefono, '+56912345678')

    def test_duplicate_enrollment_redirects_back_with_warning(self):
        """Prueba que la inscripción duplicada redirija de vuelta a detalle_taller (302) sin crear duplicado."""
        # Primera inscripción exitosa
        self.client_anonymous.post(self.enroll_url, {'nombre': 'Ana', 'email': 'ana@test.com', 'telefono': '+56911111111'})
        
        # Segunda inscripción (duplicada)
        resp2 = self.client_anonymous.post(self.enroll_url, {'nombre': 'Ana', 'email': 'ana@test.com', 'telefono': '+56911111111'})
        
        # 1. Debe redirigir de vuelta a la página de detalle del taller
        self.assertEqual(resp2.status_code, 302)
        self.assertEqual(resp2.url, self.enroll_url)
        
        # 2. Se verifica que NO se crea una segunda inscripción
        self.assertEqual(Inscripcion.objects.count(), 1)

    def test_no_cupos_redirects_back_with_error(self):
        """Prueba que al no haber cupos se redirija a detalle_taller (302)."""
        # Dejar cupos en 0
        self.taller.cupos_disponibles = 0
        self.taller.save()
        
        resp = self.client_anonymous.post(self.enroll_url, {'nombre': 'X', 'email': 'x@test.com', 'telefono': '+56922222222'})
        
        # 1. Debe redirigir de vuelta a la página de detalle del taller
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, self.enroll_url)
        
        # 2. Se verifica que NO se crea una inscripción
        self.assertEqual(Inscripcion.objects.count(), 0)