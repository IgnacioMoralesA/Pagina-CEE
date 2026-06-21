# CHECKLIST_VALIDACION.md

# Checklist de validación — CEE Conecta

## 1. Fábrica agéntica

- [ ] Existe estructura `factory/`.
- [ ] Existe CLI de fábrica.
- [ ] Existe `init-project`.
- [ ] Existe `run`.
- [ ] Existe `verify`.
- [ ] Existen agentes registrados.
- [ ] Existe arnés.
- [ ] Existe orquestador.
- [ ] Existen validadores.
- [ ] Se generan runs.
- [ ] Se generan artefactos.
- [ ] Existe reporte final.
- [ ] Los tests de fábrica pasan.

---

## 2. Documentación de coordinación

- [ ] Existe `docs/PROJECT_CONTEXT.md`.
- [ ] Existe `docs/AGENT_PROTOCOL.md`.
- [ ] Existe `docs/DECISIONS.md`.
- [ ] Existe `docs/HANDOFFS.md`.
- [ ] Existe `docs/API_CONTRACT.md`.
- [ ] Existe `docs/DATABASE_MODEL.md`.
- [ ] Existe `docs/UI_MAP.md`.

---

## 3. Base de datos

- [ ] Existe `schema.sql`.
- [ ] Existen tablas principales.
- [ ] Existen claves primarias.
- [ ] Existen claves foráneas.
- [ ] Existen constraints.
- [ ] Existen índices.
- [ ] Existe seed de roles.
- [ ] Existe documentación del modelo.

---

## 4. Backend

- [ ] Existe API FastAPI.
- [ ] Existe estructura modular.
- [ ] Existe autenticación Google.
- [ ] Existen roles.
- [ ] Existen endpoints principales.
- [ ] Existe validación de entrada.
- [ ] Existe autorización por rol.
- [ ] Existe documentación OpenAPI.
- [ ] Existen pruebas backend.

---

## 5. Frontend

- [ ] Existe proyecto React.
- [ ] Existen rutas públicas.
- [ ] Existen rutas privadas.
- [ ] Existe login.
- [ ] Existe dashboard estudiante.
- [ ] Existe dashboard admin.
- [ ] Existen formularios principales.
- [ ] Existe integración API.
- [ ] Existen validaciones visuales.

---

## 6. Seguridad

- [ ] No se almacenan contraseñas.
- [ ] No hay secretos en repositorio.
- [ ] Rutas privadas protegidas.
- [ ] Endpoints administrativos protegidos.
- [ ] Archivos validados.
- [ ] Auditoría de acciones críticas.
- [ ] Tokens manejados de forma segura.

---

## 7. Producto

- [ ] Noticias funcionales.
- [ ] Eventos funcionales.
- [ ] Solicitudes funcionales.
- [ ] Documentos funcionales.
- [ ] Finanzas básicas funcionales.
- [ ] Roles funcionales.
- [ ] Auditoría funcional.

---

## 8. Cierre técnico

- [ ] Existe reporte de pruebas.
- [ ] Existe matriz de trazabilidad.
- [ ] Existe manual técnico.
- [ ] Existe manual de usuario.
- [ ] Existe informe de cierre.
- [ ] Existe evidencia de fábrica.
