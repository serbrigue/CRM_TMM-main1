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
from django.contrib.auth import get_user_model
from crm.models import Producto, Interes, Taller, EmailLog
from decimal import Decimal
from datetime import date


class EndToEndStableFlows(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chrome_options = ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        import os
        chrome_driver_path = os.environ.get('CHROME_DRIVER_PATH')
        if chrome_driver_path and os.path.exists(chrome_driver_path):
            service = ChromeService(executable_path=chrome_driver_path)
        else:
            service = ChromeService(ChromeDriverManager().install())

        cls.selenium = webdriver.Chrome(service=service, options=chrome_options)
        cls.selenium.implicitly_wait(5)

        # create a user for login test
        User = get_user_model()
        cls.test_username = 'e2euser'
        cls.test_password = 'Password123'
        cls.test_email = 'e2euser@example.com'
        User.objects.create_user(username=cls.test_username, email=cls.test_email, password=cls.test_password)

        # create a product for cart test
        cls.product = Producto.objects.create(nombre='E2E Kit', descripcion='Kit de prueba', precio_venta=Decimal('15000'), esta_disponible=True, stock_actual=10)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.selenium.quit()
        except Exception:
            pass
        super().tearDownClass()

    def test_01_login_flow(self):
        self.selenium.get(f"{self.live_server_url}{reverse('login')}")
        wait = WebDriverWait(self.selenium, 10)
        # Fill and submit login form
        user_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="username"]')))
        pass_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="password"]')))
        user_input.send_keys(self.test_username)
        pass_input.send_keys(self.test_password)
        submit = wait.until(EC.element_to_be_clickable((By.ID, 'loginSubmit')))
        submit.click()
        # After login, header should show username
        wait.until(EC.presence_of_element_located((By.XPATH, f"//span[contains(., '{self.test_username}')]")))
        self.assertIn(self.test_username, self.selenium.page_source)

    def test_02_registration_and_welcome_email(self):
        # Choose unique username/email for test
        uname = f'reguser{int(time.time())}'
        email = f'{uname}@example.com'
        pw = 'RegPass123'

        self.selenium.get(f"{self.live_server_url}{reverse('registro_cliente')}")
        wait = WebDriverWait(self.selenium, 10)
        # Fill form fields by name attributes
        self.selenium.find_element(By.CSS_SELECTOR, 'input[name="username"]').send_keys(uname)
        # optional fields: first_name/last_name may not be present; fill email and passwords
        self.selenium.find_element(By.CSS_SELECTOR, 'input[name="email"]').send_keys(email)
        self.selenium.find_element(By.CSS_SELECTOR, 'input[name="password1"]').send_keys(pw)
        self.selenium.find_element(By.CSS_SELECTOR, 'input[name="password2"]').send_keys(pw)
        submit = wait.until(EC.element_to_be_clickable((By.ID, 'registerSubmit')))
        submit.click()

        # Wait for redirect and for the user to appear in header (logged in)
        WebDriverWait(self.selenium, 10).until(EC.presence_of_element_located((By.XPATH, f"//span[contains(., '{uname}')]")))

        # Check EmailLog for welcome email record
        found = EmailLog.objects.filter(recipient=email).exists()
        self.assertTrue(found, 'No se registró EmailLog para el registro de usuario')

    def test_03_add_to_cart_and_view_cart(self):
        # Directly visit product detail and add to cart (more stable than catalog selector)
        self.selenium.get(f"{self.live_server_url}{reverse('detalle_producto', args=[self.product.id])}")
        wait = WebDriverWait(self.selenium, 15)
        # Try several reliable selectors: data-test on form/button, fallback to class
        add_btn = None
        try:
            add_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-test="add-to-cart-{self.product.id}"]')))
        except Exception:
            try:
                # Fallback: form data-test
                form_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f'form[data-test="add-to-cart-form-{self.product.id}"]')))
            except Exception:
                # Last resort: any visible add button on the page
                print('DEBUG_PAGE_SNIPPET:', self.selenium.page_source[:2000])
                buttons = self.selenium.find_elements(By.CSS_SELECTOR, 'button.tmm-btn-add')
                if not buttons:
                    raise
                add_btn = buttons[0]

        # If we have the button element, try to click; otherwise submit the form via JS
        if add_btn is not None:
            try:
                add_btn.click()
            except Exception:
                # If click fails (overlay/stale), try JS click
                self.selenium.execute_script("arguments[0].click();", add_btn)
        else:
            # Submit the form directly via JS
                self.selenium.execute_script(
                    "var sel = 'form[data-test=\"add-to-cart-form-' + arguments[0] + '\"]'; var f = document.querySelector(" +
                    "'form[data-test=\"add-to-cart-form-' + arguments[0] + '\"]'.replace(/ /g, '')); if(f) f.submit(); else { /* try direct selector */ var sel2='form[data-test\\\\=\\\\\"add-to-cart-form-' + arguments[0] + '\\\\\" ]'; var f2 = document.querySelector(sel2); if(f2) f2.submit(); }",
                    str(self.product.id)
                )
        # After adding, go to cart and check product listed
        # Navigate to cart and verify the product is listed
        self.selenium.get(f"{self.live_server_url}{reverse('ver_carrito')}")
        WebDriverWait(self.selenium, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        self.assertIn(self.product.nombre, self.selenium.page_source)
