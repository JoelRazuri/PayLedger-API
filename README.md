# PayLedger API

Backend API orientada a la gestión de pagos, conciliación de transacciones y auditoría financiera.

El proyecto está desarrollado con FastAPI y tiene como objetivo simular una arquitectura backend moderna utilizada en sistemas financieros y SaaS, aplicando buenas prácticas de desarrollo, separación de responsabilidades y persistencia de datos relacional.

---

## Tecnologías utilizadas

- Python 3.14
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x
- Alembic
- Docker
- Pydantic
- Pytest

---

## Características actuales

- Arquitectura modular basada en features
- Configuración mediante variables de entorno
- Integración con PostgreSQL
- Migraciones versionadas con Alembic
- ORM tipado utilizando SQLAlchemy 2.x
- Validación de datos con Pydantic
- Documentación automática con Swagger/OpenAPI
- Endpoints iniciales para gestión de usuarios

---

## Estructura del proyecto

```text
app/
├── core/
├── modules/
│   └── users/
├── shared/
└── main.py