# SECURITY_REVIEW.md

# Revision de seguridad backend - CEE Conecta

**Fecha:** 2026-06-21
**Agente:** agent.security_reviewer
**Fase:** seguridad backend
**Alcance:** `app/backend/`, `tests/backend/`, contrato API, modelo de datos y documentos de coordinacion.

---

## Resultado ejecutivo

El backend FastAPI tiene una base ordenada para autenticacion y autorizacion:

- no almacena contrasenas;
- valida `aud`, correo verificado y dominio institucional configurable en Google OIDC;
- emite JWT local con expiracion;
- modela roles y permisos;
- expone dependencias `require_roles` y `require_permissions`;
- guarda hash de sesion y eventos de autenticacion exitosos;
- usa SQL parametrizado con SQLAlchemy `text`.

La revision inicial detecto dos riesgos criticos antes de habilitar endpoints de administracion, publicacion, finanzas, documentos, inventario, encuestas, votaciones o auditoria:

1. el JWT local usa un secreto por defecto conocido y no hay validacion de configuracion por ambiente;
2. la autorizacion confia exclusivamente en claims del JWT y no valida sesion, revocacion, estado actual del usuario ni permisos vigentes en base de datos.

**Estado actualizado:** al 2026-06-22, `agent.security_reviewer` valida que `SR-CRIT-001` y `SR-CRIT-002` estan resueltos por el refactor `DEC-009`. El backend puede comenzar endpoints administrativos reales solo si cada endpoint usa `require_permissions(...)`, valida permisos vigentes mediante la sesion actual y registra auditoria administrativa.

---

## Actualizacion de mitigacion - security_refactor

**Fecha:** 2026-06-22
**Agente:** agent.backend_developer
**Estado:** mitigacion revalidada por seguridad

### Hallazgos mitigados

- `SR-CRIT-001`: mitigado. `create_app()` bloquea ambientes fuera de desarrollo
  si `CEE_JWT_SECRET_KEY` esta vacio, usa `dev-only-change-me` o tiene menos de
  32 caracteres.
- `SR-CRIT-002`: mitigado. El JWT incluye `sid`; `require_auth()` valida hash de
  token, sesion activa, revocacion, expiracion, usuario `ACTIVE`, roles y permisos
  vigentes contra base de datos antes de autorizar.
- `SR-MED-002`: mitigado en la base. Errores 500 y health de base de datos no
  exponen clases internas al cliente.
- `SR-MED-005`: mitigado como servicio base. Se crea `AuditService` para login
  exitoso, login fallido, token invalido, acceso denegado y futura accion
  administrativa.
- `SR-MED-007`: mitigado. `GET /api/v1/health/database` requiere permiso vigente
  `system.admin`.

### Evidencia

- `app/backend/core/config.py`
- `app/backend/main.py`
- `app/backend/auth/jwt.py`
- `app/backend/auth/context.py`
- `app/backend/auth/dependencies.py`
- `app/backend/audit/service.py`
- `app/backend/api/v1/health.py`
- `tests/backend/test_security_base.py`
- `tests/backend/test_base_api.py`

### Pendientes no bloqueantes para comenzar endpoints administrativos

- Aplicar `require_permissions(...)` y auditoria administrativa en cada endpoint
  administrativo futuro.
- Mantener pendientes medios no abordados completamente en este avance: JWKS/OIDC
  local, rate limiting, hardening CORS/Swagger y regla de alta por padron si el
  producto la requiere.

---

## Revalidacion de riesgos criticos

**Fecha:** 2026-06-22
**Agente:** agent.security_reviewer
**Resultado:** riesgos criticos resueltos

### Validacion de `SR-CRIT-001`

Resuelto. `create_app()` ejecuta `validate_runtime_security()` y bloquea ambientes
fuera de `local`, `dev`, `development`, `test` y `testing` cuando
`CEE_JWT_SECRET_KEY` esta vacio, conserva `dev-only-change-me` o tiene menos de
32 caracteres.

### Validacion de `SR-CRIT-002`

Resuelto. Los JWT incluyen `sid`; `require_auth()` decodifica el token y luego
`AuthContextValidator` consulta base de datos para validar hash del token,
sesion existente, revocacion, expiracion, usuario `ACTIVE`, roles activos y
permisos actuales. `require_permissions(...)` autoriza con los permisos vigentes
del usuario y ya no concede bypass automatico por rol `ADMIN`.

### Pruebas ejecutadas

```bash
pytest -q tests --basetemp .pytest-basetemp
```

Resultado: `28 passed, 1 warning`.

---

## Hallazgos criticos

## SR-CRIT-001 - Secreto JWT por defecto permite forjar tokens

**Evidencia**

- `app/backend/core/config.py` define `jwt_secret_key = "dev-only-change-me"`.
- `app/backend/auth/jwt.py` firma y valida tokens HS256 con ese secreto.
- `app/backend/auth/dependencies.py` acepta roles y permisos del token decodificado.

**Impacto**

Si un ambiente no configura `CEE_JWT_SECRET_KEY`, cualquier persona con acceso al repositorio puede firmar un JWT con `roles=["ADMIN"]` y permisos arbitrarios. Esto permitiria eludir la autorizacion de futuros endpoints administrativos.

**Recomendacion**

Bloquear arranque fuera de `local/test` si:

- `CEE_JWT_SECRET_KEY` esta ausente o conserva el valor por defecto;
- el secreto no cumple longitud/entropia minima;
- `CEE_GOOGLE_CLIENT_ID` no esta configurado;
- `CEE_INSTITUTIONAL_EMAIL_DOMAIN` no esta configurado para ambientes institucionales.

## SR-CRIT-002 - Roles/permisos del JWT no se contrastan con sesion ni estado vigente

**Evidencia**

- `app/backend/auth/service.py` guarda `sessions.session_token_hash`.
- `app/backend/auth/dependencies.py` solo llama `decode_access_token`.
- `app/backend/auth/jwt.py` devuelve `UserPrincipal` con los claims `roles` y `permissions`.
- No se consulta `sessions.revoked_at`, `sessions.expires_at`, `users.status`, `user_roles.deleted_at` ni permisos actuales al proteger endpoints.

**Impacto**

Un usuario desactivado, una sesion revocada o un rol retirado podria seguir accediendo hasta la expiracion del JWT. En endpoints administrativos, esto permite mantener privilegios despues de una revocacion operacional.

**Recomendacion**

Vincular cada JWT a una sesion verificable (`jti`, `sid` o hash del token), consultar sesion activa, usuario `ACTIVE` y permisos vigentes para endpoints sensibles. Para endpoints administrativos, preferir autorizacion por permisos cargados desde base de datos o una version de permisos invalidable.

---

## Riesgos medios

## SR-MED-001 - Verificacion Google OIDC depende de `tokeninfo` y dominio por sufijo

**Evidencia**

- `app/backend/auth/google.py` usa `https://oauth2.googleapis.com/tokeninfo`.
- Se valida `aud`, `email_verified`, `email` y sufijo de dominio.
- No se valida localmente JWKS, `iss`, `exp` ni claim `hd`.

**Impacto**

`tokeninfo` puede servir para desarrollo, pero agrega dependencia de red en cada login y no deja una politica institucional tan fuerte como verificar el ID token localmente con certificados de Google y, si aplica Google Workspace, el claim `hd`.

**Recomendacion**

Usar verificacion OIDC local con libreria oficial o JWKS cacheado, validar issuer, expiracion y audiencia, y exigir `hd` cuando el dominio institucional corresponda a Google Workspace.

## SR-MED-002 - Errores 500 exponen clase de excepcion

**Evidencia**

- `app/backend/core/errors.py` incluye `exc.__class__.__name__` en respuestas 500.
- `app/backend/db/health.py` devuelve clase de excepcion en `data.detail`.

**Impacto**

El cliente puede inferir detalles internos de dependencias, drivers o fallas de infraestructura.

**Recomendacion**

Responder errores genericos al cliente y enviar detalles tecnicos solo a logs estructurados del servidor. En produccion, restringir o simplificar `GET /health/database`.

## SR-MED-003 - CORS, Swagger y configuracion no tienen guardas de produccion

**Evidencia**

- `app/backend/main.py` expone `/api/v1/docs`, `/api/v1/redoc` y `/api/v1/openapi.json` siempre.
- CORS acepta `allow_methods=["*"]`, `allow_headers=["*"]` y `allow_credentials=True`.
- `app/backend/core/config.py` no rechaza `cors_origins=["*"]` ni valores inseguros por ambiente.

**Impacto**

Una mala configuracion de origenes o documentacion publica en produccion aumenta superficie de ataque y facilita enumeracion de endpoints.

**Recomendacion**

Agregar validacion de settings por ambiente, lista explicita de origenes permitidos, y opcion para deshabilitar o proteger Swagger/OpenAPI fuera de desarrollo.

## SR-MED-004 - Falta rate limiting y auditoria completa de fallos de login

**Evidencia**

- `POST /auth/google` no tiene limitacion por IP, email o token.
- Fallos previos a la base de datos no se registran en `auth_events`.
- En `AuthService.login_google_identity`, el evento de usuario inactivo se escribe dentro de una transaccion que luego lanza `AppError`, por lo que puede quedar rollback.

**Impacto**

El endpoint de login queda expuesto a abuso, enumeracion operacional y baja trazabilidad de intentos fallidos.

**Recomendacion**

Agregar rate limiting, registrar fallos con IP/user-agent cuando sea posible y persistir eventos de fallo fuera de transacciones que se revierten.

## SR-MED-005 - Auditoria administrativa aun no esta implementada en backend

**Evidencia**

- El modelo contiene `audit_events`.
- El contexto exige que toda accion administrativa genere auditoria.
- La base backend no incluye servicio/middleware de auditoria para acciones administrativas.

**Impacto**

Endpoints administrativos futuros podrian modificar datos sin trazabilidad obligatoria.

**Recomendacion**

Antes de implementar endpoints administrativos, crear un helper de auditoria y pruebas que validen escritura en `audit_events` para acciones sensibles.

## SR-MED-006 - Alta automatica de usuarios depende solo del dominio configurado

**Evidencia**

- `AuthService._upsert_user` crea o actualiza usuario despues de OIDC valido.
- `_ensure_student_role` asigna `STUDENT` automaticamente.

**Impacto**

Si el dominio institucional es amplio, cualquier cuenta valida de ese dominio puede ingresar como estudiante. Puede ser correcto para MVP, pero debe quedar como decision explicita o complementarse con padron/lista de elegibles.

**Recomendacion**

Confirmar regla de negocio: acceso abierto por dominio institucional o acceso restringido por padron. Si se requiere padron, dejar handoff a `agent.database_designer`.

## SR-MED-007 - Health check de base de datos es publico

**Evidencia**

- `GET /api/v1/health/database` no requiere autenticacion.
- Devuelve disponibilidad de PostgreSQL y clase de excepcion.

**Impacto**

Permite a terceros observar estado de infraestructura.

**Recomendacion**

Mantener `GET /health` publico y limitar `GET /health/database` a ambientes internos, redes confiables o usuarios administrativos.

---

## Matriz de endpoints revisados

| Endpoint | Estado actual | Riesgo | Recomendacion |
| --- | --- | --- | --- |
| `GET /api/v1/health` | Publico | Bajo | Aceptable; considerar ocultar version/ambiente en produccion. |
| `GET /api/v1/health/database` | Publico | Medio | Restringir en produccion y no exponer clase de error. |
| `POST /api/v1/auth/google` | Publico | Medio | Agregar rate limiting, auditoria completa y OIDC endurecido. |
| `GET /api/v1/users/me` | Bearer JWT | Critico por JWT base | Aceptable solo tras corregir secreto y sesion para produccion. |

---

## Recomendaciones para endpoints administrativos

Para continuar con endpoints administrativos:

1. Mantener resueltos `SR-CRIT-001` y `SR-CRIT-002` mediante `DEC-009`.
2. Usar `require_permissions(...)` con permisos explicitos por endpoint; no depender solo del rol primario.
3. Agregar pruebas por endpoint para: sin token, token expirado, `STUDENT` sin permiso, rol/permisos correctos y usuario/sesion revocada.
4. Escribir evento en `audit_events` para cada accion administrativa.
5. No exponer datos sensibles de usuarios, sesiones, tokens, errores internos ni configuracion.
6. Definir controles de subida de archivos antes de implementar documentos, comprobantes o adjuntos: MIME permitido, tamano maximo, nombre seguro, almacenamiento privado y descarga autorizada.

---

## Decision de avance

**El backend puede comenzar endpoints administrativos reales bajo las condiciones de `DEC-009`.**

Puede continuar con:

- refactor de seguridad;
- pruebas;
- endpoints publicos de lectura;
- endpoints autenticados no administrativos;
- endpoints administrativos protegidos con `require_permissions(...)` y auditoria.

No debe continuar con:

- cualquier endpoint que confie en roles/permisos de JWT sin verificacion vigente.
- acciones administrativas sin registro en `audit_events`.
- endpoints de archivos sin controles de tipo, tamano, nombre seguro y descarga autorizada.
