# AGENT_PROTOCOL.md

# Protocolo de trabajo por agentes

## 1. Propósito

Este documento define cómo debe trabajar cada agente o hilo de conversación dentro del proyecto CEE Conecta.

Su objetivo es evitar inconsistencias entre base de datos, backend, frontend, QA y documentación.

---

## 2. Declaración obligatoria antes de trabajar

Antes de realizar cambios, el agente debe declarar:

```text
Agente activo:
Fase:
Objetivo específico:
Archivos que voy a leer:
Archivos que voy a modificar:
Artefactos esperados:
Dependencias con otros agentes:
Riesgos:
```

---

## 3. Formato mínimo de inicio de hilo

Cada hilo debe comenzar con un mensaje similar a:

```text
Agente activo: agent.backend_developer
Fase: backend
Objetivo: implementar API REST de CEE Conecta
Archivos permitidos: app/backend, tests/backend, docs/API_CONTRACT.md
Archivos de solo lectura: docs/PROJECT_CONTEXT.md, docs/DATABASE_MODEL.md, docs/DECISIONS.md
Archivos prohibidos: app/frontend, app/database salvo autorización
```

---

## 4. Agentes definidos

## 4.1 agent.database_designer

Responsable de:

- modelo relacional;
- tablas;
- claves primarias;
- claves foráneas;
- restricciones;
- migraciones;
- seed inicial.

Puede modificar:

- `app/database/`
- `docs/DATABASE_MODEL.md`
- `docs/DECISIONS.md`
- `docs/HANDOFFS.md`

No puede modificar:

- `app/frontend/`
- `app/backend/` salvo documentación de integración.

---

## 4.2 agent.backend_developer

Responsable de:

- API REST;
- modelos backend;
- servicios;
- controladores;
- validaciones;
- autenticación;
- autorización;
- documentación OpenAPI.

Puede modificar:

- `app/backend/`
- `tests/backend/`
- `docs/API_CONTRACT.md`
- `docs/DECISIONS.md`
- `docs/HANDOFFS.md`

No puede modificar:

- `app/frontend/`
- `app/database/schema.sql` sin handoff al agente de base de datos.

---

## 4.3 agent.frontend_developer

Responsable de:

- interfaz web;
- rutas;
- componentes;
- formularios;
- integración con API;
- validaciones visuales.

Puede modificar:

- `app/frontend/`
- `docs/UI_MAP.md`
- `docs/HANDOFFS.md`
- `docs/DECISIONS.md`

No puede modificar:

- `app/backend/`
- `app/database/`

No puede inventar endpoints. Si necesita uno, debe registrarlo como handoff hacia `agent.backend_developer`.

---

## 4.4 agent.qa_engineer

Responsable de:

- plan de pruebas;
- pruebas unitarias;
- pruebas de integración;
- pruebas e2e;
- checklist;
- reporte de cobertura;
- matriz de trazabilidad.

Puede modificar:

- `tests/`
- `docs/CHECKLIST_VALIDACION.md`
- `docs/TRACEABILITY_MATRIX.md`
- `docs/HANDOFFS.md`
- `docs/DECISIONS.md`

---

## 4.5 agent.security_reviewer

Responsable de:

- revisión de autenticación;
- revisión de autorización;
- exposición de datos;
- validación de archivos;
- control de roles;
- secretos;
- endpoints protegidos.

Puede modificar:

- `docs/SECURITY_REVIEW.md`
- `docs/HANDOFFS.md`
- `docs/DECISIONS.md`
- tests relacionados con seguridad.

---

## 4.6 agent.documenter

Responsable de:

- README;
- instalación;
- manual técnico;
- manual de usuario;
- cierre técnico;
- evidencia final.

Puede modificar:

- `README.md`
- `docs/`
- `project/runs/` solo para reportes finales, si corresponde.

---

## 5. Regla de handoff

Cuando un agente deja trabajo para otro, debe agregar una entrada en `docs/HANDOFFS.md`.

Formato:

```markdown
## Handoff N

**Fecha:** YYYY-MM-DD  
**De:** agent.nombre_origen  
**Para:** agent.nombre_destino  
**Estado:** pendiente | recibido | resuelto  

### Contexto

Explicación breve.

### Entregables

- archivo 1
- archivo 2

### Decisiones relevantes

- decisión 1
- decisión 2

### Acción requerida

Qué debe hacer el siguiente agente.
```

---

## 6. Regla de decisiones

Toda decisión técnica que afecte a más de un hilo debe registrarse en `docs/DECISIONS.md`.

Ejemplos:

- cambio de stack;
- cambio de nombres de tablas;
- cambio de estados;
- nuevo endpoint;
- nueva regla de negocio;
- cambio de estructura de carpetas;
- cambio de autenticación;
- cambio de modelo de datos.

---

## 7. Regla de consistencia

Cada agente debe respetar:

- `docs/PROJECT_CONTEXT.md`
- `docs/DECISIONS.md`
- `docs/API_CONTRACT.md`
- `docs/DATABASE_MODEL.md`
- `docs/UI_MAP.md`
- `docs/HANDOFFS.md`

---

## 8. Regla de alcance

Un agente solo puede modificar archivos de su dominio.

Si necesita modificar un archivo fuera de su alcance:

1. debe explicar por qué;
2. debe pedir autorización;
3. debe dejar una decisión o handoff;
4. no debe ejecutar el cambio hasta ser autorizado.

---

## 9. Regla de cierre de avance

Al finalizar cada avance, el agente debe entregar:

```text
Agente activo:
Resumen:
Archivos modificados:
Decisiones registradas:
Handoffs creados:
Pruebas ejecutadas:
Errores encontrados:
Pendientes:
Siguiente agente recomendado:
```

---

## 10. Regla de pruebas

Todo cambio funcional debe incluir o actualizar pruebas.

Si no se agregan pruebas, el agente debe justificarlo.

---

## 11. Regla de seguridad

Está prohibido:

- guardar secretos;
- exponer tokens;
- dejar credenciales en archivos;
- desactivar autenticación sin justificación;
- permitir acceso administrativo sin rol;
- aceptar archivos sin validar tipo y tamaño;
- permitir SQL dinámico inseguro.

---

## 12. Regla de trazabilidad

Cada módulo debe poder relacionarse con:

- requisito;
- tabla;
- endpoint;
- pantalla;
- prueba;
- evidencia.

---

## 13. Comando esperado de validación

Cuando corresponda, ejecutar:

```bash
pytest -q tests
```

Para frontend, cuando exista:

```bash
npm test
npm run build
```

---

## 14. Prioridad de documentos

Si hay conflicto entre documentos, usar este orden:

1. `docs/DECISIONS.md`
2. `docs/PROJECT_CONTEXT.md`
3. `docs/API_CONTRACT.md`
4. `docs/DATABASE_MODEL.md`
5. `docs/UI_MAP.md`
6. `docs/HANDOFFS.md`
