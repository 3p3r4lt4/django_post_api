# Django POS API 🏪

API REST profesional para sistema **Punto de Venta (POS)** con integración SUNAT vía **Nubefact**.

Migrado y mejorado desde `flask-pos-api` (TECSUP) incorporando el patrón del proyecto `django_barbershop`.

---

## Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Framework | Django 5.1 + Django REST Framework |
| Autenticación | JWT (SimpleJWT) con blacklist |
| Base de datos | PostgreSQL 17 |
| Facturación electrónica | Nubefact API JSON v2.9 (SUNAT) |
| Documentación | Swagger UI (drf-spectacular) |
| Zona horaria | America/Lima (UTC-5) |

---

## Estructura del Proyecto

```
django_pos_api/
├── config/
│   ├── settings.py       # Configuración centralizada
│   ├── urls.py           # URLs raíz
│   └── wsgi.py
├── core/
│   ├── nubefact.py       # Servicio Nubefact (4 operaciones SUNAT)
│   ├── permissions.py    # IsAdmin, IsAdminOrReadOnly
│   └── utils.py          # now_lima(), calcular_igv(), etc.
├── apps/
│   ├── authentication/   # Registro, Login, JWT, Perfiles
│   ├── productos/        # CRUD productos y servicios
│   ├── clientes/         # CRUD clientes (DNI/RUC)
│   ├── ventas/           # Ventas multi-producto + Comprobantes
│   └── reportes/         # Dashboards y resúmenes
├── manage.py
├── requirements.txt
└── .env.example
```

---

## Instalación

```bash
# 1. Clonar y entrar al proyecto
cd django_pos_api

# 2. Crear entorno virtual e instalar dependencias
python -m venv venv
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate           # Windows

pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con tu DB y credenciales Nubefact

# 4. Crear la base de datos en PostgreSQL
psql -U postgres -c "CREATE DATABASE mini_pos;"

# 5. Aplicar migraciones
python manage.py migrate

# 6. Crear superusuario
python manage.py createsuperuser

# 7. Levantar servidor
python manage.py runserver
```

---

## Documentación interactiva

| URL | Descripción |
|---|---|
| `http://localhost:8000/api/docs/` | Swagger UI |
| `http://localhost:8000/api/redoc/` | ReDoc |
| `http://localhost:8000/admin/` | Django Admin |

---

## Endpoints

### 🔐 Autenticación — `/api/auth/`

| Método | Ruta | Descripción | Auth |
|---|---|---|---|
| POST | `/api/auth/register/` | Registrar usuario | Público |
| POST | `/api/auth/login/` | Login → tokens JWT | Público |
| POST | `/api/auth/refresh/` | Renovar access token | Público |
| POST | `/api/auth/logout/` | Blacklist del refresh token | JWT |
| GET | `/api/auth/me/` | Perfil del usuario actual | JWT |
| PATCH | `/api/auth/me/` | Actualizar perfil propio | JWT |
| GET | `/api/auth/users/` | Listar usuarios | Admin |
| PATCH | `/api/auth/users/<id>/` | Cambiar rol/estado | Admin |

**Login request:**
```json
{ "username": "admin", "password": "123456" }
```
**Login response:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "usuario": { "id": 1, "username": "admin", "rol": "admin" }
}
```

---

### 📦 Productos — `/api/productos/`

| Método | Ruta | Descripción | Auth |
|---|---|---|---|
| GET | `/api/productos/` | Listar productos activos | JWT |
| POST | `/api/productos/` | Crear producto | Admin |
| GET | `/api/productos/<id>/` | Detalle | JWT |
| PUT/PATCH | `/api/productos/<id>/` | Actualizar | Admin |
| DELETE | `/api/productos/<id>/` | Soft-delete | Admin |

**Filtros:** `?categoria=Ropa`, `?es_servicio=true`, `?search=laptop`

**Crear producto:**
```json
{
  "nombre": "Laptop HP",
  "precio": 2999.00,
  "stock": 10,
  "categoria": "Electrónica",
  "es_servicio": false,
  "codigo": "LAP-001"
}
```

---

### 👥 Clientes — `/api/clientes/`

| Método | Ruta | Descripción | Auth |
|---|---|---|---|
| GET | `/api/clientes/` | Listar clientes | JWT |
| POST | `/api/clientes/` | Crear cliente | JWT |
| GET | `/api/clientes/<id>/` | Detalle | JWT |
| PUT/PATCH | `/api/clientes/<id>/` | Actualizar | JWT |
| DELETE | `/api/clientes/<id>/` | Soft-delete | JWT |

**Tipos de documento:**
- `"1"` → DNI (persona natural → genera **Boleta**)
- `"6"` → RUC (empresa → genera **Factura**)
- `"-"` → Varios (ventas sin documento)

**Crear cliente:**
```json
{
  "tipo_documento": "1",
  "numero_documento": "12345678",
  "nombre": "Juan Perez",
  "email": "juan@gmail.com",
  "telefono": "987654321"
}
```

---

### 🛒 Ventas — `/api/ventas/`

| Método | Ruta | Descripción | Auth |
|---|---|---|---|
| GET | `/api/ventas/` | Listar ventas | JWT |
| POST | `/api/ventas/` | Nueva venta | JWT |
| GET | `/api/ventas/<id>/` | Detalle | JWT |
| POST | `/api/ventas/<id>/anular/` | Anular venta + baja SUNAT | Admin |
| POST | `/api/ventas/<id>/comprobante/emitir/` | Emitir comprobante | JWT |
| GET | `/api/ventas/<id>/comprobante/consultar/` | Consultar estado SUNAT | JWT |
| GET | `/api/ventas/<id>/comprobante/consultar-anulacion/` | Consultar estado baja | JWT |

**Crear venta (multi-producto con comprobante):**
```json
{
  "cliente_id": 1,
  "items": [
    { "producto_id": 1, "cantidad": 2 },
    { "producto_id": 3, "cantidad": 1 }
  ],
  "medio_de_pago": "EFECTIVO",
  "observaciones": "Entrega inmediata",
  "emitir_comprobante": true
}
```

**Respuesta exitosa con comprobante:**
```json
{
  "message": "Venta registrada exitosamente.",
  "venta": {
    "id": 42,
    "total": 350.00,
    "comprobante": {
      "tipo_label": "Boleta",
      "serie": "BBB1",
      "numero": 1,
      "enlace_pdf": "https://www.nubefact.com/cpe/xxxx.pdf",
      "aceptada_por_sunat": true
    }
  }
}
```

**Descuento por volumen automático:**
| Cantidad | Descuento |
|---|---|
| >= 10 | 5% |
| >= 20 | 10% |
| >= 50 | 15% |

**Anular venta:**
```json
{ "motivo": "ERROR EN EL PEDIDO" }
```

---

### 📊 Reportes — `/api/reportes/`

| Método | Ruta | Descripción | Auth |
|---|---|---|---|
| GET | `/api/reportes/ventas/` | Resumen por período | Admin |
| GET | `/api/reportes/productos/top/` | Top productos | Admin |
| GET | `/api/reportes/diario/` | Resumen del día | Admin |
| GET | `/api/reportes/comprobantes/` | Estado comprobantes | Admin |

**Parámetros comunes:** `?fecha_inicio=2025-01-01&fecha_fin=2025-01-31`

---

## Integración Nubefact (SUNAT)

El módulo `core/nubefact.py` implementa las **4 operaciones** de la API JSON v2.9:

### Operación 1: Generar comprobante
- Se dispara automáticamente al crear una venta con `emitir_comprobante: true`
- Si el cliente tiene RUC → **Factura** (serie `FFF1`)
- Si el cliente tiene DNI o sin doc → **Boleta** (serie `BBB1`)
- Cálculo automático de IGV (18%), valor unitario sin IGV, subtotales por línea

### Operación 2: Consultar comprobante
```
GET /api/ventas/<id>/comprobante/consultar/
```
Consulta el estado en SUNAT y actualiza el registro local.

### Operación 3: Generar anulación (comunicación de baja)
```
POST /api/ventas/<id>/anular/
Body: { "motivo": "..." }
```
Anula la venta localmente Y envía la comunicación de baja a SUNAT.

### Operación 4: Consultar anulación
```
GET /api/ventas/<id>/comprobante/consultar-anulacion/
```

---

## Variables de Entorno

| Variable | Descripción | Default |
|---|---|---|
| `SECRET_KEY` | Clave secreta Django | (requerido en prod) |
| `DEBUG` | Modo debug | `True` |
| `DB_NAME` | Nombre de la BD | `mini_pos` |
| `DB_USER` | Usuario PostgreSQL | `postgres` |
| `DB_PASSWORD` | Contraseña PostgreSQL | `postgres` |
| `DB_HOST` | Host PostgreSQL | `localhost` |
| `JWT_ACCESS_TOKEN_MINUTES` | Expiración access token | `60` |
| `JWT_REFRESH_TOKEN_DAYS` | Expiración refresh token | `7` |
| `NUBEFACT_URL` | URL de la empresa en Nubefact | (requerido) |
| `NUBEFACT_TOKEN` | Token de autenticación | (requerido) |
| `NUBEFACT_SERIE_BOLETA` | Serie para boletas | `BBB1` |
| `NUBEFACT_SERIE_FACTURA` | Serie para facturas | `FFF1` |

---

## Diferencias con el flask-pos-api original

| Característica | Flask POS (original) | Django POS (mejorado) |
|---|---|---|
| Framework | Flask + Flask-RESTful | Django 5.1 + DRF |
| Items por venta | 1 solo producto | ✅ Multi-producto |
| Clientes | ❌ No existe | ✅ Modelo completo DNI/RUC |
| Comprobantes | ❌ No existe | ✅ Boleta y Factura |
| Nubefact | ❌ No integrado | ✅ 4 operaciones completas |
| Reportes | ❌ No existe | ✅ 4 reportes |
| Anulación | ❌ No existe | ✅ Con baja SUNAT |
| Servicios | ❌ No distingue | ✅ Flag `es_servicio` (no descuenta stock) |
| Swagger | ❌ No existe | ✅ Auto-generado |
| Logout | ❌ No existe | ✅ Blacklist JWT |

---

## Autor

**Eduardo Peralta** — Coordinador de Sistemas, FIBERLUX TECH S.A.C.  
Proyecto TECSUP — Arquitectura de Software / Fullstack Python
