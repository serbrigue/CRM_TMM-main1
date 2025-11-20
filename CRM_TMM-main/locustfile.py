from locust import HttpUser, task, between, events
import random
import os
from datetime import datetime
import csv
import threading
import time

# Credentials pool loaded from `locust_users.csv` when available.
CREDENTIALS = []
_creds_lock = threading.Lock()
_next_cred = 0

def load_credentials():
    """Load credentials from `LOCUST_USERS_FILE` (defaults to `locust_users.csv`).
    Falls back to generating a predictable pool from env vars if the file is missing.
    """
    global CREDENTIALS
    path = os.getenv('LOCUST_USERS_FILE', 'locust_users.csv')
    if os.path.exists(path):
        try:
            with open(path, newline='') as f:
                reader = csv.reader(f)
                creds = [(r[0].strip(), r[1].strip()) for r in reader if r and len(r) >= 2]
                if creds:
                    CREDENTIALS = creds
                    return
        except Exception:
            # If parsing fails, fall through to generated pool
            CREDENTIALS = []

    # Fallback generated pool (same default behavior as before)
    user_count = int(os.getenv('LOCUST_USER_COUNT', '100'))
    prefix = os.getenv('LOCUST_USER_PREFIX', 'locust')
    default_pwd = os.getenv('LOCUST_USER_PASSWORD', 'locustpass')
    CREDENTIALS = [(f"{prefix}{i}", default_pwd) for i in range(1, max(1, user_count) + 1)]


def assign_credential():
    """Assign the next credential from the loaded pool in a thread-safe round-robin manner.
    This reduces login storms by spreading logins across different test accounts
    in the order users start. In distributed setups each process will have its
    own counter; that's still a significant improvement over everyone using
    the same account at once.
    """
    global _next_cred
    with _creds_lock:
        if not CREDENTIALS:
            return None
        cred = CREDENTIALS[_next_cred % len(CREDENTIALS)]
        _next_cred += 1
        return cred

# URL del detalle del taller activo para la prueba de inscripción.
# NOTA: Debes asegurar que este ID de taller exista y esté activo en tu base de datos de prueba.
TALLER_ID_ACTIVO = 1  # Asumiendo que el taller de prueba más antiguo tiene ID 1
# Development-friendly ID ranges (use these when discovery fails)
TALLER_ID_MIN = 1
TALLER_ID_MAX = 5
PRODUCT_ID_MIN = 1
PRODUCT_ID_MAX = 3

class TMMUser(HttpUser):
    """Define el comportamiento de un usuario simulado en el CRM de TMM."""
    
    # Tiempo de espera entre peticiones, simula el "pensamiento" del usuario (1 a 2.5 segundos)
    wait_time = between(1, 2.5)

    def on_start(self):
        """Se ejecuta al inicio de cada usuario simulado."""
        self.client_name = f"StressUser_{random.randint(10000, 99999)}"
        self.client_email = f"stress.test.{random.randint(10000, 99999)}@e2e.cl"
        # Default enroll URL; will try to discover a valid taller dynamically
        self.enroll_url = f"/talleres/{TALLER_ID_ACTIVO}/"
        # Keep a dynamic enroll id to reflect the actually chosen taller in logs
        self.enroll_id = str(TALLER_ID_ACTIVO)
        # Load credentials pool (file or generated fallback) and assign one
        # credential deterministically (round-robin per-process) to avoid
        # login storms when many users start at once.
        try:
            load_credentials()
            cred = assign_credential()
            if cred:
                self.test_username, self.test_password = cred
            else:
                # fallback env-driven
                user_count = int(os.getenv('LOCUST_USER_COUNT', '100'))
                prefix = os.getenv('LOCUST_USER_PREFIX', 'locust')
                default_pwd = os.getenv('LOCUST_USER_PASSWORD', 'locustpass')
                uid = random.randint(1, max(1, user_count))
                self.test_username = getattr(self, 'test_username', f"{prefix}{uid}")
                self.test_password = getattr(self, 'test_password', default_pwd)
        except Exception:
            # If anything odd happens, fall back to previous random selection
            user_count = int(os.getenv('LOCUST_USER_COUNT', '100'))
            prefix = os.getenv('LOCUST_USER_PREFIX', 'locust')
            default_pwd = os.getenv('LOCUST_USER_PASSWORD', 'locustpass')
            uid = random.randint(1, max(1, user_count))
            self.test_username = getattr(self, 'test_username', f"{prefix}{uid}")
            self.test_password = getattr(self, 'test_password', default_pwd)
        self.logged_in = False
        # Stagger startup slightly so many users don't all attempt login at the exact same microsecond
        try:
            time.sleep(random.uniform(0, float(os.getenv('LOCUST_STARTUP_JITTER', '0.5'))))
        except Exception:
            pass
        try:
            # GET login page to obtain CSRF token/cookies
            login_get = self.client.get('/login/', name='Login GET')
            try:
                csrf = self.client.cookies.get('csrftoken') or getattr(login_get, 'cookies', {}).get('csrftoken')
            except Exception:
                csrf = None
            headers = {}
            if csrf:
                headers['X-CSRFToken'] = csrf
                headers['Referer'] = 'http://web:8000/login/'
            creds = {'username': self.test_username, 'password': self.test_password}
            with self.client.post('/login/', data=creds, headers=headers if headers else None, catch_response=True, name='Login POST') as r:
                # Django usually redirects (302) on successful login to LOGIN_REDIRECT_URL
                if getattr(r, 'status_code', None) in (302, 200):
                    self.logged_in = True
                else:
                    self._fire_request_failure('Login POST', Exception(f'Login failed status={getattr(r, "status_code", None)}'))
        except Exception as e:
            # Non-fatal: mark not logged and continue as anonymous
            self._fire_request_failure('Login Flow', e, request_type='GET', response_time=0)

    def _fire_request_failure(self, name, exception, request_type="GET", response_time=0):
        """Try to report a request failure to Locust's event system.
        Falls back to printing if the events API isn't available in this runtime.
        """
        try:
            events.request_failure.fire(request_type=request_type, name=name, response_time=response_time, exception=exception)
            return
        except Exception:
            pass
        # Try environment events if available
        try:
            self.environment.events.request_failure.fire(request_type=request_type, name=name, response_time=response_time, exception=exception)
            return
        except Exception:
            pass
        # Last resort: print the failure so it's visible in logs
        try:
            print(f"REQUEST_FAILURE fallback: {request_type} {name} -> {exception}")
        except Exception:
            pass

    @task(1)
    def browse_home_and_catalog(self):
        """Simula la navegación a la página de inicio y el catálogo de talleres (Lectura ligera)."""
        self.client.get("/", name="1. Home")
        # Wrap GETs in try/except to catch server errors and report failures
        try:
            self.client.get("/productos/", name="2. Catalogo Productos (Lectura)")
        except Exception as e:
            self._fire_request_failure("2. Catalogo Productos (Lectura)", e, request_type="GET", response_time=0)
            return
        try:
            self.client.get("/talleres/", name="3. Catalogo Talleres (Lectura)")
        except Exception as e:
            self._fire_request_failure("3. Catalogo Talleres (Lectura)", e, request_type="GET", response_time=0)
            return

    @task(2)
    def enroll_in_taller(self):
        """
        Simula la inscripción anónima a un taller (Operación de Escritura crítica).
        Tiene el doble de peso (task(2)) que la navegación, ya que es el flujo más importante.
        """
        # 1. Preparar datos únicos para cada intento de inscripción
        data = {
            'nombre': self.client_name,
            'email': self.client_email,
            'telefono': f'+569{random.randint(10000000, 99999999)}',
            # CSRF es manejado automáticamente por Locust si la sesión es válida, pero 
            # como es anónimo, la prueba se centra en la lógica de POST.
        }

        # 2. Asegurarse de que `self.enroll_url` apunte a un taller existente.
        # Intentamos descubrir dinámicamente un taller válido desde el catálogo.
        # Try to discover a valid taller id from the catalog page; if discovery
        # fails, fall back to the configured range to avoid 404s during stress tests.
        try:
            catalog_resp = self.client.get('/talleres/', name='4. GET Catalogo Talleres')
            import re
            matches = re.findall(r'/talleres/(\d+)/', catalog_resp.text)
            if matches:
                chosen = random.choice(matches)
                self.enroll_url = f"/talleres/{chosen}/"
                self.enroll_id = str(chosen)
            else:
                # fallback to configured range
                chosen = str(random.randint(TALLER_ID_MIN, TALLER_ID_MAX))
                self.enroll_url = f"/talleres/{chosen}/"
                self.enroll_id = str(chosen)
        except Exception as e:
            # If the catalog request errors (500 etc), choose from the fallback range
            self._fire_request_failure('4. GET Catalogo Talleres', e, request_type="GET", response_time=0)
            chosen = str(random.randint(TALLER_ID_MIN, TALLER_ID_MAX))
            self.enroll_url = f"/talleres/{chosen}/"

        # 3. Primero hacer GET para obtener la cookie/CSRF token (igual que un navegador)
        # Esto evita el 403 por CSRF cuando el endpoint espera el token en POST.
        # GET the enroll page defensively
        # Always perform an inline login attempt to ensure session+CSRF cookie
        # are present for the enrollment POST. This guarantees the form includes
        # the CSRF cookie even if earlier attempts didn't persist session state.
        try:
            login_get = self.client.get('/login/', name='Login GET (inline)')
            try:
                csrf_login = self.client.cookies.get('csrftoken') or getattr(login_get, 'cookies', {}).get('csrftoken')
            except Exception:
                csrf_login = None
            headers_login = {}
            if csrf_login:
                headers_login['X-CSRFToken'] = csrf_login
                headers_login['Referer'] = 'http://web:8000/login/'
            creds = {'username': self.test_username, 'password': self.test_password}
            with self.client.post('/login/', data=creds, headers=headers_login if headers_login else None, catch_response=True, name='Login POST (inline)') as lr:
                # log cookie state after login attempt for debugging
                try:
                    print(f"[locust-debug] after inline login cookies={self.client.cookies.get_dict()}")
                except Exception:
                    pass
                if getattr(lr, 'status_code', None) in (302, 200):
                    self.logged_in = True
                else:
                    self._fire_request_failure('Login POST (inline)', Exception(f'Login failed status={getattr(lr, "status_code", None)}'))
        except Exception as e:
            self._fire_request_failure('Login Flow (inline)', e, request_type='GET', response_time=0)
        try:
            get_resp = self.client.get(self.enroll_url, name=f"4. GET Inscripcion Taller {self.enroll_id}")
        except Exception as e:
            self._fire_request_failure(f"4. GET Inscripcion Taller {self.enroll_id}", e, request_type="GET", response_time=0)
            return
        # Obtener token desde cookies (nombre por defecto de Django: 'csrftoken')
        csrf_token = None
        try:
            csrf_token = self.client.cookies.get('csrftoken') or get_resp.cookies.get('csrftoken')
        except Exception:
            csrf_token = None

        # If cookie was not set, try to find the CSRF token inside the page HTML
        # (hidden input named 'csrfmiddlewaretoken') and use that as a fallback.
        if not csrf_token:
            try:
                import re
                m = re.search(r"name=[\"']csrfmiddlewaretoken[\"']\s+value=[\"']([^\"']+)[\"']", getattr(get_resp, 'text', '') or '')
                if m:
                    csrf_token = m.group(1)
                    # ensure the token is present in the session cookies as Django
                    # often checks the cookie in addition to the header
                    try:
                        # requests' cookiejar supports set; this helps Django accept the POST
                        self.client.cookies.set('csrftoken', csrf_token)
                    except Exception:
                        pass
            except Exception:
                pass

        headers = {}
        if csrf_token:
            headers['X-CSRFToken'] = csrf_token
            # Añadir Referer ayuda a pasar algunas comprobaciones CSRF basadas en referer
            headers['Referer'] = f"http://web:8000{self.enroll_url}"
        # Debug: print cookies and header presence before POST
        try:
            print(f"[locust-debug] enroll_id={self.enroll_id} csrf_token_present={bool(csrf_token)} cookies={self.client.cookies.get_dict()}")
        except Exception:
            pass

        # 3. Enviar la petición POST usando catch_response para poder marcar fallos correctamente
        # El endpoint de inscripción redirige (302) a /pago/<inscripcion_id> si es exitoso.
        with self.client.post(
            self.enroll_url,
            data=data,
            name=f"4. POST Inscripcion Taller {self.enroll_id}",
            catch_response=True,
            headers=headers if headers else None,
        ) as response:
            # Defensive: sometimes the request may fail before a response object
            # is produced (network error, connection refused, etc.). In that
            # case `response` can be falsy or lack attributes and calling
            # `response.failure()` raises a LocustError. Handle that scenario
            # by firing a request_failure event instead.
            if not response or getattr(response, 'status_code', None) is None:
                ex = Exception('No response returned from POST request')
                self._fire_request_failure(f"4. POST Inscripcion Taller {self.enroll_id}", ex, request_type="POST", response_time=0)
                return

            # Validamos según la URL final (Locust sigue redirecciones por defecto)
            if response.status_code == 200:
                if "/pago/" in response.url:
                    # Éxito: Redirigió a la página de pago
                    response.success()
                elif "/talleres/" in response.url:
                    # Éxito controlado: Redirigió de vuelta al taller (ya inscrito o sin cupos)
                    response.success()
                elif "/login/" in response.url:
                    response.failure("Fallo: Redirigido a login (Usuario no autenticado)")
                else:
                    response.failure(f"Error inesperado: URL final {response.url}")
            elif response.status_code == 302:
                # Si por alguna razón no siguió la redirección
                if "/pago/" in response.headers.get('Location', ''):
                    response.success()
                elif self.enroll_url in response.headers.get('Location', ''):
                    response.success()
                else:
                    response.failure(f"Redirección inesperada: {response.headers.get('Location')}")
            else:
                response.failure(f"Error HTTP: {response.status_code}")