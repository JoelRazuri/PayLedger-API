# PayLedger API — Contexto del proyecto

## 1. Propósito

PayLedger API es una plataforma backend de control financiero y conciliación para empresas. Registra las operaciones informadas por una empresa cliente, conserva su impacto contable interno y, en una etapa posterior, las comparará con datos de bancos, proveedores o procesadores externos simulados.

PayLedger **no es un banco ni una billetera**: no custodia, recibe ni transfiere dinero real. Su objetivo es aportar trazabilidad, clasificación contable y detección de diferencias.

El dominio se divide de esta manera:

- **Payments** representa la operación informada por la empresa.
- **Ledger** registra el impacto contable de un pago completado.
- **Reconciliation** comparará los registros locales con una fuente externa.
- **Audit** registrará las acciones relevantes realizadas en el sistema.

El proyecto también tiene un propósito educativo: practicar procesos habituales de sistemas financieros mediante FastAPI, PostgreSQL, SQLAlchemy y una arquitectura modular.

---

## 2. Alcance de la primera versión

| Capacidad | Estado |
|---|---|
| Gestión y validación de usuarios | Implementada |
| Registro, inicio de sesión y perfil autenticado | Implementada |
| Creación, consulta, procesamiento y cancelación de pagos | Implementada |
| Asientos contables de doble entrada | Implementada |
| Conciliación con un proveedor simulado | Pendiente |
| Auditoría básica | Pendiente |

Queda fuera del alcance inicial:

- movimiento o custodia de dinero real;
- procesamiento de tarjetas e integraciones bancarias productivas;
- facturación fiscal;
- aplicación frontend;
- microservicios;
- múltiples organizaciones, roles y permisos avanzados;
- tipos de cambio y contabilidad multimoneda por operación.

---

## 3. Arquitectura

El proyecto utiliza una arquitectura modular por funcionalidad:

```text
app/
├── core/                 # configuración y conexión a la base de datos
├── modules/
│   ├── users/
│   ├── auth/
│   ├── payments/
│   └── ledger/
├── shared/               # excepciones y utilidades compartidas
└── main.py               # creación de FastAPI y registro de routers
```

Cada módulo utiliza, según sus necesidades:

| Archivo | Responsabilidad |
|---|---|
| `model.py` | Entidades y tablas de SQLAlchemy |
| `schema.py` | Contratos de entrada, salida y filtros con Pydantic |
| `service.py` | Reglas de negocio y acceso simple a datos |
| `router.py` | Endpoints HTTP y traducción de errores de dominio |
| `exceptions.py` | Excepciones propias del módulo |
| `enums.py` | Valores cerrados del dominio |

Se mantiene un enfoque directo y Pythonic, sin una capa `repository` prematura. Los servicios no dependen de HTTP: `HTTPException` y los códigos de respuesta pertenecen a los routers.

---

## 4. Tecnologías y ejecución

- Python 3.14
- FastAPI y Swagger/OpenAPI
- PostgreSQL 16
- SQLAlchemy 2.x
- Alembic
- Pydantic v2
- Pytest
- Ruff
- Docker y Docker Compose

La aplicación puede utilizar **una instancia local de PostgreSQL o la instancia de Docker Compose**. Son alternativas de ejecución; sus credenciales pueden ser diferentes y `DATABASE_URL` determina cuál utiliza la API.

Las migraciones de Alembic versionan los cambios de `users`, credenciales, fechas con zona horaria, `payments`, `journal_entries` y `ledger_entries`.

---

## 5. Módulos implementados

### Users

Gestiona el modelo de usuario, normaliza el email y valida que el nombre tenga entre 2 y 255 caracteres. La creación de usuarios pertenece a Auth; Users conserva las consultas públicas actuales.

```http
GET /users
GET /users/{user_id}
```

### Auth

Registra usuarios con contraseña hasheada, autentica credenciales, emite JWT y resuelve el perfil actual. Los usuarios inactivos no pueden iniciar sesión ni utilizar endpoints protegidos.

```http
POST /auth/register
POST /auth/login
GET  /auth/me
```

### Payments

Permite crear y consultar pagos propios, procesarlos mediante un proveedor sandbox o cancelarlos. La creación exige `Idempotency-Key`; repetir la misma solicitud devuelve el pago existente y reutilizar la clave con otro contenido produce un conflicto.

El proveedor simula éxito, rechazo de negocio y falla técnica. Las transiciones concurrentes se protegen para que una acción solo pueda reclamar un pago pendiente una vez.

```http
POST /payments
GET  /payments
GET  /payments/{payment_id}
POST /payments/{payment_id}/process
POST /payments/{payment_id}/cancel
```

El listado admite paginación y filtros por estado, proveedor y moneda.

### Ledger

Es un registro contable **inmutable y de solo lectura**. Al completar un pago se crea, dentro de la misma transacción local, un asiento con exactamente dos movimientos balanceados:

- débito en `PAYMENT_EXPENSE`;
- crédito en `EXTERNAL_FUNDS`.

Los pagos rechazados, fallidos o cancelados no generan asientos. La base de datos refuerza el balance, la unicidad y la correspondencia de importes y monedas mediante restricciones y triggers diferidos.

```http
GET /ledger/journals
GET /ledger/journals/{journal_id}
GET /ledger/payments/{payment_id}/journal
```

Las consultas requieren JWT, solo exponen recursos del usuario autenticado y normalizan `occurred_at` y `created_at` explícitamente a UTC. El listado admite paginación y filtros por moneda y cuenta.

---

## 6. Persistencia actual

| Tabla | Responsabilidad |
|---|---|
| `users` | Identidad, credenciales hasheadas, estado y fechas del usuario |
| `payments` | Pago local, propietario, clave idempotente, destinatario, estado y resultado del proveedor |
| `journal_entries` | Cabecera del asiento asociado al evento de un pago completado |
| `ledger_entries` | Movimientos débito y crédito que componen el asiento |

Los modelos de Reconciliation y Audit se definirán cuando se diseñen esos módulos; este documento no anticipa tablas ni endpoints que todavía no existen.

---

## 7. Reglas vigentes

- Utilizar type hints y código simple, legible y Pythonic.
- Mantener la separación modular y la lógica de negocio fuera de los routers.
- No almacenar ni exponer contraseñas en texto plano.
- Proteger los recursos propios mediante JWT y aislamiento por usuario.
- Responder con `404` para recursos inexistentes o pertenecientes a otro usuario cuando corresponda.
- Crear y revisar migraciones de Alembic ante cambios de persistencia.
- Mantener idempotencia y control de concurrencia en operaciones sensibles.
- Crear asientos únicamente para pagos completados y de forma atómica con su finalización local.
- Representar explícitamente en UTC las fechas expuestas por la API.
- Ejecutar pruebas automatizadas en cada bloque y una comprobación manual integral al final del módulo, antes de su cierre.
- Usar commits convencionales con descripción en español: `feat:`, `fix:`, `docs:`, `test:` o `chore:`.

---

## 8. Estado y documentación de cambios

Los módulos Users, Auth, Payments y Ledger están implementados. Auth, Payments y Ledger completaron su flujo SDD y sus artefactos se conservan en:

```text
openspec/changes/archive/
├── 2026-08-05-validate-user-full-name/
├── 2026-08-06-add-authentication/
├── 2026-08-10-add-payments-module/
└── 2026-08-27-add-ledger-module/
```

Los documentos archivados contienen las propuestas, especificaciones, diseños, tareas y evidencias de verificación de cada cambio. Deben consultarse para conocer reglas detalladas; el código y las migraciones siguen siendo la fuente de verdad del estado ejecutable.

---

## 9. Próximos pasos

El siguiente módulo es **Reconciliation**. Antes de implementarlo se deben definir, como mínimo:

1. el formato de las operaciones externas simuladas;
2. la clave utilizada para vincularlas con pagos locales;
3. las reglas de coincidencia y discrepancia;
4. los estados y el historial de cada conciliación;
5. los endpoints y permisos de consulta o ejecución.

Después se implementará **Audit** y se realizará una prueba integral de la primera versión de la API.

---

## 10. Uso de este documento

Este archivo ofrece contexto general para onboarding y continuidad entre sesiones. No reemplaza las especificaciones de cada módulo ni pretende ser documentación exhaustiva de la API.

Antes de modificar el proyecto, se deben revisar este documento, los artefactos SDD relevantes y el código actual para confirmar que el contexto continúa vigente.
