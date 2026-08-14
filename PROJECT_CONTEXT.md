# PayLedger API — Contexto del Proyecto

## 1. Descripción

PayLedger API es un backend desarrollado con FastAPI para registrar pagos, movimientos financieros y procesos de conciliación.

La aplicación no recibe ni transfiere dinero. Su función es registrar las operaciones realizadas en el sistema, consultar o recibir información de proveedores externos de pago y verificar que ambas fuentes coincidan.

### Rol financiero de PayLedger

PayLedger representa una plataforma de control financiero contratada por
empresas para registrar sus operaciones, mantener un ledger interno y
conciliarlas contra información proveniente de bancos, proveedores y
procesadores externos simulados.

No es un banco, una billetera ni custodia o transfiere dinero real. Los importes
se originan en la empresa cliente y en sus sistemas externos. PayLedger conserva
una representación de esas operaciones para aportar trazabilidad, clasificación
contable, comparación y detección de diferencias.

Esta perspectiva determina cómo deben interpretarse las cuentas, los débitos y
los créditos del módulo Ledger. Payments describe la operación informada por la
empresa; Ledger registra su impacto contable interno; Reconciliation compara
esos registros con la fuente externa correspondiente.

Ejemplos de proveedores externos:

- Mercado Pago
- Ualá
- Stripe
- Bancos o procesadores de pago

El sistema deberá permitir detectar diferencias de importe, estado, moneda o identificador entre una operación local y la información reportada por el proveedor.

Este proyecto también busca aplicar buenas prácticas de backend moderno con Python, FastAPI, PostgreSQL, SQLAlchemy y una arquitectura modular.

---

## 2. Objetivos principales

- Gestionar usuarios y autenticación.
- Registrar y consultar pagos.
- Mantener un historial de movimientos mediante un ledger.
- Conciliar operaciones locales contra operaciones externas.
- Detectar inconsistencias.
- Registrar acciones importantes mediante auditoría.
- Proteger endpoints mediante autenticación JWT.
- Mantener código modular, tipado y fácil de probar.

---

## 3. Alcance

La primera versión incluirá:

- gestión de usuarios;
- autenticación mediante email, contraseña y JWT;
- registro y consulta de pagos;
- movimientos de crédito y débito;
- conciliación contra proveedores simulados;
- auditoría básica;
- PostgreSQL y migraciones con Alembic;
- documentación mediante Swagger;
- pruebas automatizadas progresivas.

Queda fuera del alcance inicial:

- mover dinero real;
- procesar tarjetas;
- integraciones bancarias productivas;
- facturación fiscal;
- aplicación frontend;
- arquitectura de microservicios.

---

## 4. Arquitectura

El proyecto utiliza una estructura modular por funcionalidad.

```text
app/
├── core/
├── modules/
│   ├── users/
│   ├── auth/
│   ├── payments/
│   ├── ledger/
│   ├── reconciliation/
│   └── audit/
├── shared/
└── main.py
```

Cada módulo puede contener la siguiente estructura:

```text
model.py
schema.py
service.py
router.py
exceptions.py
```

### Responsabilidad de cada archivo

- **model.py:** define las entidades y tablas de la base de datos utilizando SQLAlchemy.
- **schema.py:** define los modelos de entrada y salida (DTOs) mediante Pydantic.
- **service.py:** contiene la lógica de negocio y el acceso simple a datos.
- **router.py:** expone los endpoints HTTP y traduce las excepciones del negocio a respuestas HTTP.
- **exceptions.py:** contiene excepciones propias del dominio del módulo.
- **main.py:** crea la aplicación FastAPI y registra todos los routers.

Actualmente el proyecto sigue un enfoque **Pythonic**, por lo que todavía no se utiliza una capa `repository`. Si en el futuro las consultas se vuelven complejas o aparecen múltiples fuentes de datos, podrá incorporarse sin modificar la lógica del negocio.

Los servicios no deben depender de HTTP. Las respuestas HTTP (`HTTPException`, códigos de estado, etc.) pertenecen únicamente a la capa de `router`.

---

## 5. Tecnologías

- Python 3.14
- FastAPI
- PostgreSQL 16
- SQLAlchemy 2.x
- Alembic
- Pydantic v2
- Docker y Docker Compose
- Pytest
- Ruff
- Swagger / OpenAPI

---

## 6. Tablas previstas

### users

- id
- email
- full_name
- hashed_password
- is_active
- created_at
- updated_at

Almacena los usuarios del sistema.

---

### payments

- id
- external_id
- provider
- amount
- currency
- status
- description
- created_by
- created_at
- updated_at

Representa los pagos registrados localmente.

---

### ledger_entries

- id
- payment_id
- entry_type
- concept
- amount
- currency
- created_by
- created_at

Representa cada movimiento financiero interno.

---

### reconciliations

- id
- payment_id
- external_reference
- local_amount
- external_amount
- local_status
- external_status
- result
- details
- reconciled_at

Guarda el resultado de una conciliación.

---

### audit_logs

- id
- user_id
- action
- entity_type
- entity_id
- previous_data
- new_data
- created_at

Registra acciones relevantes realizadas dentro del sistema.

> El diseño detallado de cada tabla se definirá durante el desarrollo de cada módulo.

---

## 7. Endpoints previstos

### Users

```http
POST /users
GET /users
GET /users/{user_id}
```

### Auth

```http
POST /auth/login
GET /auth/me
```

### Payments

```http
POST /payments
GET /payments
GET /payments/{payment_id}
PATCH /payments/{payment_id}/status
```

### Ledger

```http
POST /ledger/entries
GET /ledger/entries
GET /ledger/payments/{payment_id}/entries
```

### Reconciliation

```http
POST /reconciliations
GET /reconciliations
GET /reconciliations/{reconciliation_id}
GET /reconciliations/issues
```

### Audit

```http
GET /audit
```

Estos endpoints representan el alcance previsto del proyecto. El diseño de requests, responses, validaciones y reglas de negocio se definirá al implementar cada módulo.

---

## 8. Reglas generales

- Utilizar type hints.
- Mantener una arquitectura modular.
- Los routers no deben contener lógica de negocio.
- Los services no deben lanzar `HTTPException`.
- Los mensajes HTTP deberán estar escritos en español.
- Nunca almacenar contraseñas en texto plano.
- No exponer información sensible en las respuestas.
- Crear migraciones con Alembic cuando cambien los modelos.
- Revisar las migraciones antes de ejecutarlas.
- Priorizar código simple, legible y Pythonic.
- Agregar pruebas automatizadas de manera progresiva.

---

## 9. Estado actual

Actualmente el proyecto cuenta con:

- FastAPI configurado.
- PostgreSQL mediante Docker.
- SQLAlchemy.
- Alembic.
- Variables de entorno.
- Swagger.
- Arquitectura modular.

El único módulo implementado hasta el momento es **users**.

Incluye:

- Modelo.
- Schemas.
- Service.
- Router.
- Excepciones.
- Creación de usuarios.
- Listado de usuarios.
- Validación de email duplicado.
- Respuestas HTTP adecuadas (`201 Created` y `409 Conflict`).

Último commit:

```text
feat: agregar validaciones de negocio y manejo de errores para usuarios
```

Los módulos **auth**, **payments**, **ledger**, **reconciliation** y **audit** todavía se encuentran pendientes.

---

## 10. Próximos pasos

El siguiente módulo a desarrollar será **auth**.

Antes de implementarlo será necesario:

1. Agregar contraseña al registro de usuarios.
2. Incorporar `hashed_password` al modelo.
3. Agregar el campo `is_active`.
4. Hashear la contraseña antes de almacenarla.
5. Crear la migración correspondiente.
6. Implementar JWT.
7. Crear los endpoints `/auth/login` y `/auth/me`.
8. Implementar la dependencia `get_current_user`.

Luego se continuará con el siguiente orden de desarrollo:

```text
payments
↓
ledger
↓
reconciliation
↓
audit
```

---

## 11. Uso de este documento

Este documento tiene como objetivo brindar el contexto general del proyecto y servir como guía durante el desarrollo.

No pretende definir en detalle todas las reglas funcionales o técnicas. Cada módulo será analizado y diseñado en profundidad antes de su implementación, definiendo sus modelos, relaciones, validaciones, endpoints y decisiones de arquitectura en ese momento.

Cualquier asistente o herramienta (por ejemplo, Codex) debe utilizar este documento únicamente como referencia general y revisar siempre el código existente antes de realizar modificaciones o agregar nuevas funcionalidades.
