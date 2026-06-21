# UI_MAP.md

# Mapa inicial de interfaz — CEE Conecta

## 1. Propósito

Este documento define las pantallas, rutas y flujos iniciales del frontend.

El frontend debe respetar este mapa y no crear nuevas pantallas sin registrarlas.

---

## 2. Zonas de la aplicación

## Zona pública

Visible sin iniciar sesión.

## Zona privada

Requiere login institucional.

## Zona administrativa

Requiere rol administrativo o directiva.

---

## 3. Rutas públicas

| Ruta | Pantalla | Descripción |
|---|---|---|
| `/` | Inicio | Página principal del CEE |
| `/noticias` | Noticias | Listado de noticias |
| `/noticias/:id` | Detalle noticia | Visualización de noticia |
| `/comunicados` | Comunicados | Listado de comunicados |
| `/eventos` | Eventos | Calendario/listado de actividades |
| `/eventos/:id` | Detalle evento | Información de evento e inscripción |
| `/directiva` | Directiva | Integrantes del CEE |
| `/documentos` | Documentos públicos | Archivos públicos |
| `/transparencia` | Transparencia | Resumen financiero y actas públicas |
| `/contacto` | Contacto | Datos de contacto |

---

## 4. Rutas de autenticación

| Ruta | Pantalla | Descripción |
|---|---|---|
| `/login` | Login | Ingreso con Google institucional |
| `/auth/callback` | Callback | Procesamiento de autenticación |
| `/perfil` | Perfil | Datos del usuario |

---

## 5. Rutas estudiante

| Ruta | Pantalla | Descripción |
|---|---|---|
| `/app` | Dashboard estudiante | Resumen personal |
| `/app/solicitudes` | Mis solicitudes | Listado propio |
| `/app/solicitudes/nueva` | Nueva solicitud | Formulario |
| `/app/solicitudes/:id` | Detalle solicitud | Seguimiento |
| `/app/eventos` | Eventos internos | Eventos disponibles |
| `/app/documentos` | Documentos | Documentos visibles |
| `/app/votaciones` | Votaciones | Votaciones abiertas |
| `/app/encuestas` | Encuestas | Encuestas disponibles |

---

## 6. Rutas directiva/admin

| Ruta | Pantalla | Descripción |
|---|---|---|
| `/admin` | Dashboard admin | Resumen administrativo |
| `/admin/noticias` | Gestión noticias | CRUD publicaciones |
| `/admin/noticias/nueva` | Editor noticia | Crear noticia |
| `/admin/eventos` | Gestión eventos | CRUD eventos |
| `/admin/eventos/nuevo` | Editor evento | Crear evento |
| `/admin/solicitudes` | Gestión solicitudes | Revisión |
| `/admin/solicitudes/:id` | Revisión solicitud | Resolver solicitud |
| `/admin/reuniones` | Reuniones | Gestión |
| `/admin/actas` | Actas | Documentos de reunión |
| `/admin/acuerdos` | Acuerdos | Seguimiento |
| `/admin/finanzas` | Finanzas | Resumen |
| `/admin/finanzas/ingresos` | Ingresos | Registro |
| `/admin/finanzas/gastos` | Gastos | Registro |
| `/admin/inventario` | Inventario | Recursos |
| `/admin/prestamos` | Préstamos | Control recursos |
| `/admin/documentos` | Documentos admin | Gestión |
| `/admin/encuestas` | Encuestas admin | Gestión |
| `/admin/votaciones` | Votaciones admin | Gestión |
| `/admin/usuarios` | Usuarios | Roles |
| `/admin/auditoria` | Auditoría | Logs |
| `/admin/configuracion` | Configuración | Parámetros |

---

## 7. Componentes base

- `PublicLayout`
- `AdminLayout`
- `StudentLayout`
- `Navbar`
- `Sidebar`
- `Footer`
- `ProtectedRoute`
- `RoleGuard`
- `DataTable`
- `StatusBadge`
- `ConfirmDialog`
- `FileUploader`
- `Pagination`
- `SearchInput`
- `DateRangePicker`
- `EmptyState`
- `LoadingState`
- `ErrorState`

---

## 8. Flujos UI principales

## Crear solicitud

```text
Dashboard estudiante
→ Mis solicitudes
→ Nueva solicitud
→ Formulario
→ Confirmación
→ Detalle solicitud
```

## Publicar noticia

```text
Dashboard admin
→ Gestión noticias
→ Nueva noticia
→ Guardar borrador
→ Publicar
→ Ver noticia pública
```

## Inscribirse a evento

```text
Eventos
→ Detalle evento
→ Inscribirme
→ Confirmación
→ Mis eventos
```

## Registrar gasto

```text
Dashboard admin
→ Finanzas
→ Gastos
→ Nuevo gasto
→ Adjuntar comprobante
→ Guardar
→ Auditoría
```

---

## 9. Reglas frontend

- No mostrar botones administrativos a estudiantes.
- Validar campos obligatorios antes de enviar.
- Mostrar mensajes claros de error.
- No asumir que una acción fue exitosa sin respuesta de API.
- Usar estados visuales coherentes.
- Proteger rutas privadas.
- Manejar sesión expirada.
- No almacenar tokens sensibles en localStorage si se usa cookie HttpOnly.

---

## 10. Pendientes del agente frontend

El agente `agent.frontend_developer` debe:

1. Crear estructura de React.
2. Crear layouts.
3. Crear rutas.
4. Crear pantallas base.
5. Crear servicios API.
6. Crear guards.
7. Crear formularios iniciales.
8. Registrar decisiones.
9. Dejar handoffs para backend si faltan endpoints.
