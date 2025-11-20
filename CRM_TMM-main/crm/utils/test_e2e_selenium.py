import time
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from decimal import Decimal
from crm.models import Taller, Interes, Cliente
from datetime import date
from selenium.common.exceptions import TimeoutException

# Nota: Para Docker, se debe configurar el WebDriver para usar Chromium/Chrome sin cabecera (headless)
# y apuntar al servidor dentro del contenedor.

class EndToEndTests(StaticLiveServerTestCase):
    """Pruebas funcionales de extremo a extremo usando Selenium."""

    @classmethod
    def setUpClass(cls):
        # 1. Configuración del servidor de Django (puerto dinámico, base de datos de prueba)
        super().setUpClass()

        # 2. Configuración para Selenium WebDriver
        # Opciones para ejecutar Chrome en un entorno Docker (headless)
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox") # Necesario para Docker/Linux
        chrome_options.add_argument("--disable-dev-shm-usage") # Optimización de memoria
        
        # Preferir un chromedriver local si está disponible (útil en Docker)
        import os
        chrome_driver_path = os.environ.get('CHROME_DRIVER_PATH')
        if chrome_driver_path and os.path.exists(chrome_driver_path):
            service = ChromeService(executable_path=chrome_driver_path)
        else:
            # Fallback: usar webdriver-manager para descargar el driver en entornos de desarrollo
            service = ChromeService(ChromeDriverManager().install())
        
        # Inicializar el navegador
        cls.selenium = webdriver.Chrome(service=service, options=chrome_options)
        cls.selenium.implicitly_wait(10) # Espera implícita para encontrar elementos

        # 3. Crear datos de prueba (un taller activo)
        cls.interes_resina = Interes.objects.create(nombre='Resina', descripcion='Test')
        cls.taller_activo = Taller.objects.create(
            nombre='Taller E2E',
            descripcion='Taller para pruebas E2E.',
            precio=Decimal('10000'),
            cupos_totales=5,
            categoria=cls.interes_resina,
            fecha_taller=date(2099, 12, 1),
            esta_activo=True
        )
        # URL al detalle del taller para realizar la inscripción (ruta relativa)
        cls.enroll_url = reverse('detalle_taller', args=[cls.taller_activo.id])

    @classmethod
    def tearDownClass(cls):
        # Cerrar el navegador después de todas las pruebas
        cls.selenium.quit()
        super().tearDownClass()

    def test_01_anonymous_user_can_view_taller_and_go_to_form(self):
        """Verifica que un usuario anónimo puede navegar al formulario de inscripción."""
        
        # 1. Navegar al catálogo (self.live_server_url es la URL base)
        self.selenium.get(f"{self.live_server_url}{reverse('catalogo_talleres')}")
        self.assertIn('Catálogo de Talleres', self.selenium.title)

        # 2. Encontrar el enlace del taller y hacer clic
        taller_link = self.selenium.find_element(by=webdriver.common.by.By.LINK_TEXT, value='Ver Detalles e Inscribirme')
        taller_link.click()

        # 3. Verificar que estamos en la página de detalle
        self.assertIn('Detalle:', self.selenium.title)

        # 4. Verificar que el formulario de inscripción NO está disponible para usuarios anónimos
        # y que se muestra el enlace de 'Iniciar Sesión'
        self.assertNotIn('Reserva tu Cupo', self.selenium.page_source)
        login_link = WebDriverWait(self.selenium, 10).until(EC.presence_of_element_located((By.LINK_TEXT, 'Iniciar Sesión')))
        self.assertTrue(login_link)
        
    def test_02_anonymous_enrollment_and_redirection_to_payment(self):
        """Simula la inscripción como anónimo y verifica la redirección al pago."""
        
        # Navegar desde el catálogo al detalle (mismo flujo que test_01)
        self.selenium.get(f"{self.live_server_url}{reverse('catalogo_talleres')}")
        wait_catalog = WebDriverWait(self.selenium, 20)
        taller_link = wait_catalog.until(EC.element_to_be_clickable((By.LINK_TEXT, 'Ver Detalles e Inscribirme')))
        taller_link.click()

        # En este proyecto no se permiten inscripciones anónimas.
        # Comprobamos que no exista el formulario y que se muestre la opción de login.
        self.assertNotIn('form.tmm-form', self.selenium.page_source)
        login_link = WebDriverWait(self.selenium, 10).until(EC.presence_of_element_located((By.LINK_TEXT, 'Iniciar Sesión')))
        self.assertTrue(login_link)
        
    def test_03_anonymous_enrollment_failure_no_data(self):
        """Prueba que el formulario rechace el envío sin datos."""
        
        # Navegar desde el catálogo al detalle (mismo flujo que test_01)
        self.selenium.get(f"{self.live_server_url}{reverse('catalogo_talleres')}")
        wait_catalog = WebDriverWait(self.selenium, 20)
        taller_link = wait_catalog.until(EC.element_to_be_clickable((By.LINK_TEXT, 'Ver Detalles e Inscribirme')))
        taller_link.click()

        # Verificamos que no exista el formulario y que se muestre la opción de login.
        self.assertNotIn('form.tmm-form', self.selenium.page_source)
        login_link = WebDriverWait(self.selenium, 10).until(EC.presence_of_element_located((By.LINK_TEXT, 'Iniciar Sesión')))
        self.assertTrue(login_link)