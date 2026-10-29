# PayLedger API — Contexto del proyecto

## 1. Propósito

PayLedger API es una plataforma backend de control financiero y conciliación para empresas. Registra las operaciones informadas por una empresa cliente, conserva su impacto contable interno y las compara con operaciones de proveedores externos simulados.

PayLedger **no es un banco ni una billetera**: no custodia, recibe ni transfiere dinero real. Su objetivo es aportar trazabilidad, clasificación contable y detección de diferencias.

El dominio se divide de esta manera:

- **Payments** representa la operación informada por la empresa.
- **Ledger** registra el impacto contable de un pago completado.
- **Reconciliation** compara los registros locales con evidencia de una fuente externa simulada.
- **Audit** registra de forma inmutable las acciones financieras relevantes y sus resultados.

El proyecto también tiene un propósito educativo: practicar procesos habituales de sistemas financieros mediante FastAPI, PostgreSQL, SQLAlchemy y una arquitectura modular.

---

## 2. Alcance de la primera versión

| Capacidad | Estado |
|---|---|
| Gestión y validación de usuarios | Implementada |
| Registro, inicio de sesión y perfil autenticado | Implementada |
| Creación, consulta, procesamiento y cancelación de pagos | Implementada |
| Asientos contables de doble entrada | Implementada |
| Conciliación con un proveedor simulado | Implementada |
| Auditoría básica | Implementada |

La **v1 está cerrada**. El 29 de octubre de 2026 se completó la comprobación manual integral de Auth, Payments, Ledger, Reconciliation y Audit sobre una misma operación financiera.

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
│   ├── ledger/
│   ├── reconciliation/
│   └── audit/
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

Las migraciones de Alembic versionan los cambios de `users`, credenciales, fechas con zona horaria, `payments`, `journal_entries`, `ledger_entries`, `external_transactions`, `reconciliations` y `audit_events`.

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

### Reconciliation

Registra evidencia terminal proveniente de proveedores externos simulados y la compara explícitamente con los pagos locales. La evidencia es inmutable e idempotente por propietario, proveedor e identificador externo.

El matching utiliza propietario, proveedor y `provider_payment_id`. Cada ejecución conserva snapshots locales y externos de importe, moneda y estado, y produce uno de estos resultados:

- `matched`: todos los valores coinciden;
- `mismatched`: existe el pago, pero uno o más valores difieren;
- `unmatched`: no existe un pago local correspondiente.

Las conciliaciones son append-only. `Idempotency-Key` distingue un reintento de una nueva ejecución deliberada, incluso ante solicitudes concurrentes.

```http
POST /external-transactions
GET  /external-transactions
GET  /external-transactions/{external_transaction_id}
POST /external-transactions/{external_transaction_id}/reconcile
GET  /reconciliations
GET  /reconciliations/{reconciliation_id}
```

Todos los endpoints requieren JWT, aíslan datos por usuario y normalizan las fechas expuestas a UTC. Los listados admiten paginación y las conciliaciones pueden filtrarse por resultado.

### Audit

Conserva un historial inmutable de las acciones financieras relevantes realizadas por usuarios autenticados. Registra el actor, la acción, el recurso, el resultado, un código de motivo para fallos de negocio y detalles construidos por el servidor mediante listas permitidas.

Audita la creación, procesamiento y cancelación de pagos, la recepción de evidencia externa y la ejecución de conciliaciones. Los éxitos se persisten atómicamente con la operación de negocio; los fallos esperados se registran después del rollback. No conserva contraseñas, JWT, cuerpos HTTP sin procesar ni otros secretos.

```http
GET /audit-events
GET /audit-events/{audit_event_id}
```

Las consultas requieren JWT, aíslan eventos por usuario y responden `404` tanto para identificadores inexistentes como ajenos. El listado admite paginación y filtros por acción, tipo e identificador de recurso, resultado y rango temporal. La base de datos impide actualizar o eliminar eventos mediante triggers.

---

## 6. Persistencia actual

| Tabla | Responsabilidad |
|---|---|
| `users` | Identidad, credenciales hasheadas, estado y fechas del usuario |
| `payments` | Pago local, propietario, clave idempotente, destinatario, estado y resultado del proveedor |
| `journal_entries` | Cabecera del asiento asociado al evento de un pago completado |
| `ledger_entries` | Movimientos débito y crédito que componen el asiento |
| `external_transactions` | Evidencia inmutable recibida de proveedores externos simulados |
| `reconciliations` | Intentos append-only con resultados, snapshots y claves idempotentes |
| `audit_events` | Historial inmutable de acciones financieras, actores, recursos y resultados |

Las tablas financieras de Ledger, Reconciliation y Audit son append-only o inmutables según las reglas de cada módulo. PostgreSQL refuerza estas garantías mediante restricciones, índices y triggers, además de las validaciones de la aplicación.

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

Los módulos Users, Auth, Payments, Ledger, Reconciliation y Audit están implementados. Sus cambios completados conservan los artefactos de planificación, implementación y verificación en:

```text
openspec/changes/archive/
├── 2026-08-05-validate-user-full-name/
├── 2026-08-06-add-authentication/
├── 2026-08-10-add-payments-module/
├── 2026-08-27-add-ledger-module/
├── 2026-10-07-add-reconciliation-module/
└── 2026-10-29-add-audit-module/
```

Los documentos archivados contienen las propuestas, especificaciones, diseños, tareas y evidencias de verificación de cada cambio. Deben consultarse para conocer reglas detalladas; el código y las migraciones siguen siendo la fuente de verdad del estado ejecutable.

Reconciliation cumple funcionalmente sus 8 requisitos y 15 escenarios, con 181 pruebas automatizadas y una comprobación manual integral aprobadas. Su archivo conserva un `verify-report.md` con `FAIL` y un `process-exception.md`: la limitación corresponde a evidencia histórica incompleta del proceso Strict TDD, no a un defecto funcional conocido.

Audit cumple sus 6 requisitos y 15 escenarios. La verificación final ejecutó 191 pruebas automatizadas y la comprobación manual validó el flujo completo, los filtros, el aislamiento entre usuarios y la respuesta indistinguible para eventos ajenos o inexistentes.

La validación integral de la v1 confirmó el registro y la autenticación, el ciclo de vida de pagos, la generación de un asiento balanceado, la conciliación con evidencia externa y la trazabilidad completa mediante eventos de auditoría.

---

## 9. Próximos pasos

La primera versión está finalizada. Los próximos cambios deben comenzar como funcionalidades de una versión posterior y justificarse mediante un nuevo flujo SDD.

Las posibles evoluciones incluyen organizaciones, roles, permisos avanzados, soporte multimoneda y nuevas capacidades de observabilidad. Ninguna forma parte del alcance cerrado de la v1.

---

## 10. Uso de este documento

Este archivo ofrece contexto general para onboarding y continuidad entre sesiones. No reemplaza las especificaciones de cada módulo ni pretende ser documentación exhaustiva de la API.

Antes de modificar el proyecto, se deben revisar este documento, los artefactos SDD relevantes y el código actual para confirmar que el contexto continúa vigente.
