## Quick orientation

This is a small Django app (Django 5.x) that implements a CRM + workshops + product sales site.
Key repo roots:
- Project settings: `tmm_project/settings.py` (SQLite by default, `MEDIA_ROOT` at `/media`, `STATICFILES_DIRS` -> `/static`).
- Main app: `crm/` (models, views, forms, admin, templates).
- Templates: `crm/templates/crm/` (Spanish UI).  
- Dev requirements: `requirements.txt` (`django`, `pillow`).

Run patterns (dev):
- Install deps and start dev server from project root:
  - python -m pip install -r requirements.txt
  - python manage.py migrate
  - python manage.py runserver
- Create a superuser or use the sample created by `crm/populate_data.py`.
- Populate realistic test data (script is self-contained):
  - python crm/populate_data.py
    - The script configures Django (adds project path + `DJANGO_SETTINGS_MODULE`) so run it from project root.

Important high-level architecture points
- Single Django app `crm` holds domain logic: models (Cliente, Empresa, Taller, Inscripcion, Producto, VentaProducto, DetalleVenta, Interes), views, templates and admin.
- Data flows:
  - Enrollment flow: user -> `detalle_taller_inscripcion` -> creates `Inscripcion` and decrements `Taller.cupos_disponibles` using transactions + `select_for_update()` to avoid races.
  - E‑commerce flow: session-based cart (see `views.get_carrito`, `agregar_a_carrito`, `finalizar_compra`), stock validation via `select_for_update()` and `F()` updates, creation of `VentaProducto` + `DetalleVenta`.
  - Email is sent via Django `send_mail`; dev backend is `console.EmailBackend` in settings (check `tmm_project/settings.py`).

Conventions & gotchas (codebase-specific)
- Language/locale: Spanish (`LANGUAGE_CODE = 'es-cl'`, `TIME_ZONE = 'America/Santiago'`) — expect Spanish labels and messages in templates.
- Session cart shape: stored under `request.session['carrito']` as a dict mapping product id strings to { 'cantidad': int, 'precio': str }.
  - Prices are stored as strings in the session and converted to Decimal in views. Keep this pattern when reading/writing the cart.
- Concurrency: critical operations (enrollment, stock changes) use `transaction.atomic()` and `select_for_update()`; preserve this pattern to avoid race conditions.
- Unique constraint: `Inscripcion` has `unique_together = ('cliente','taller')` — code handles `IntegrityError` when duplicates occur.
- Authentication: uses Django's built-in auth URLs (`django.contrib.auth.urls` is included). Login URL is `/login/` by default.
- Media files: images for products and workshops are uploaded to `media/productos/` and `media/talleres/`. During DEBUG the project serves media via `urlpatterns += static(...)`.

Where to look for behaviors/examples
- Enrollment and payment simulation: `crm/views.py` functions `detalle_taller_inscripcion` and `pago_simulado`.
- Cart & checkout: `agregar_a_carrito`, `ver_carrito`, `finalizar_compra` in `crm/views.py`.
- Admin customizations and B2B additions: `crm/admin.py` (Empresa model admin, Cliente raw_id_fields for `empresa`).
- Data model: `crm/models.py` (read field names, verbose names and choices). Use the model docstrings — they are authoritative here.
- Test data generator: `crm/populate_data.py` (creates Empresas, Clientes B2B/B2C, Talleres, Inscripciones, Productos, Ventas). Useful for local testing.

Examples for quick edits
- To add a new view route, register it in `crm/urls.py` and add a template under `crm/templates/crm/`.
- To update stock behavior, follow `finalizar_compra` pattern: validate with `select_for_update()`, accumulate updates, create sale, then update stock using `F()` and `update_fields`.

Tests & verification
- There are no CI pipelines in the repo. Quick manual checks:
  - python manage.py makemigrations && python manage.py migrate
  - python manage.py runserver and try the UI (or run `crm/populate_data.py` then log in as `admin_tmm` if created).
  - Use `python manage.py test` to run Django tests (if/when added).

Editing guidance for AI agents
- Be conservative with DB migrations: if you add/rename fields, include migration generation and minimal data-preserving changes.
- Preserve transaction blocks and `select_for_update()` in code paths that change stock or cupos. These are intentional concurrency controls.
- Keep message strings in Spanish and follow existing template variable names (e.g., `fechas_cursos_activas`, `talleres_recomendados`, `carrito`).
- When modifying the cart, ensure session keys remain strings for product IDs.

If anything in this guidance is unclear or you want more examples (e.g., a runnable dev checklist, recommended unit test skeletons, or common fix patterns), tell me which area to expand and I will iterate.
