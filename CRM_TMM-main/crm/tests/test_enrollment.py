from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from crm.models import Taller, Interes, Cliente, Inscripcion
from datetime import date


class EnrollmentTests(TestCase):

    def setUp(self):
        # Crear interés y taller
        self.interes = Interes.objects.create(nombre='Test', descripcion='desc')
        self.taller = Taller.objects.create(
            nombre='Taller Test', descripcion='desc', precio=Decimal('10000'),
            cupos_totales=2, categoria=self.interes, fecha_taller=date(2025,12,1), esta_activo=True
        )

    def test_anonymous_enrollment_success(self):
        url = reverse('api_enroll_taller', args=[self.taller.id])
        data = {'nombre': 'Ana', 'email': 'ana@test.com', 'telefono': '+56912345678'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Inscripcion.objects.count(), 1)
        self.taller.refresh_from_db()
        self.assertEqual(self.taller.cupos_disponibles, self.taller.cupos_totales - 1)
        cliente = Cliente.objects.get(email='ana@test.com')
        self.assertEqual(cliente.telefono, '+56912345678')

    def test_duplicate_enrollment_returns_409(self):
        # Primera inscripción
        Cliente.objects.create(nombre_completo='Ana', email='ana@test.com')
        self.client.post(reverse('api_enroll_taller', args=[self.taller.id]), {'nombre': 'Ana', 'email': 'ana@test.com', 'telefono': '+56911111111'})
        # Segunda inscripción (duplicada)
        resp2 = self.client.post(reverse('api_enroll_taller', args=[self.taller.id]), {'nombre': 'Ana', 'email': 'ana@test.com', 'telefono': '+56911111111'})
        self.assertIn(resp2.status_code, (400, 409))

    def test_no_cupos_returns_400(self):
        # Dejar cupos en 0
        self.taller.cupos_disponibles = 0
        self.taller.save()
        resp = self.client.post(reverse('api_enroll_taller', args=[self.taller.id]), {'nombre': 'X', 'email': 'x@test.com', 'telefono': '+56922222222'})
        self.assertEqual(resp.status_code, 400)
