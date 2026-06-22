-- CEE Conecta - Initial seed data
-- Agent: agent.database_designer
-- Date: 2026-06-21

BEGIN;

INSERT INTO roles (name, display_name, description, is_system)
VALUES
    ('STUDENT', 'Estudiante', 'Usuario autenticado con correo institucional.', TRUE),
    ('BOARD_MEMBER', 'Integrante directiva', 'Integrante general de la directiva del CEE.', TRUE),
    ('PRESIDENT', 'Presidente', 'Presidente del Centro de Estudiantes.', TRUE),
    ('TREASURER', 'Tesorero', 'Responsable de finanzas y transparencia.', TRUE),
    ('SECRETARY', 'Secretario', 'Responsable de actas, documentos y acuerdos.', TRUE),
    ('ADMIN', 'Administrador', 'Administrador tecnico y funcional del sistema.', TRUE)
ON CONFLICT (name) DO UPDATE
SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    is_system = EXCLUDED.is_system,
    updated_at = now();

INSERT INTO permissions (code, module, action, description, is_system)
VALUES
    ('users.manage', 'users', 'manage', 'Administrar usuarios.', TRUE),
    ('roles.manage', 'roles', 'manage', 'Administrar roles y permisos.', TRUE),
    ('content.publish', 'content', 'publish', 'Crear y publicar noticias o comunicados.', TRUE),
    ('events.manage', 'events', 'manage', 'Administrar eventos.', TRUE),
    ('events.register', 'events', 'register', 'Inscribirse en eventos.', TRUE),
    ('requests.create', 'requests', 'create', 'Crear solicitudes estudiantiles.', TRUE),
    ('requests.manage', 'requests', 'manage', 'Gestionar solicitudes estudiantiles.', TRUE),
    ('documents.manage', 'documents', 'manage', 'Gestionar documentos y versiones.', TRUE),
    ('finances.manage', 'finances', 'manage', 'Gestionar presupuestos, ingresos y gastos.', TRUE),
    ('inventory.manage', 'inventory', 'manage', 'Gestionar inventario y prestamos.', TRUE),
    ('meetings.manage', 'meetings', 'manage', 'Gestionar reuniones, actas y acuerdos.', TRUE),
    ('surveys.manage', 'surveys', 'manage', 'Gestionar encuestas.', TRUE),
    ('votings.manage', 'votings', 'manage', 'Gestionar votaciones.', TRUE),
    ('audit.view', 'audit', 'view', 'Consultar eventos de auditoria.', TRUE),
    ('system.admin', 'system', 'admin', 'Administrar configuracion del sistema.', TRUE)
ON CONFLICT (code) DO UPDATE
SET
    module = EXCLUDED.module,
    action = EXCLUDED.action,
    description = EXCLUDED.description,
    is_system = EXCLUDED.is_system,
    updated_at = now();

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN ('events.register', 'requests.create')
WHERE r.name = 'STUDENT'
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'content.publish',
    'events.manage',
    'requests.manage',
    'documents.manage',
    'inventory.manage',
    'meetings.manage',
    'surveys.manage',
    'votings.manage',
    'audit.view'
)
WHERE r.name = 'BOARD_MEMBER'
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'users.manage',
    'content.publish',
    'events.manage',
    'requests.manage',
    'documents.manage',
    'finances.manage',
    'inventory.manage',
    'meetings.manage',
    'surveys.manage',
    'votings.manage',
    'audit.view'
)
WHERE r.name = 'PRESIDENT'
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN ('finances.manage', 'documents.manage', 'audit.view')
WHERE r.name = 'TREASURER'
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN ('documents.manage', 'meetings.manage', 'content.publish', 'audit.view')
WHERE r.name = 'SECRETARY'
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'ADMIN'
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO student_centers (name, slug, description, is_active)
VALUES ('CEE Conecta', 'cee-conecta', 'Centro de Estudiantes base para el MVP.', TRUE)
ON CONFLICT (slug) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    updated_at = now();

INSERT INTO positions (name, description, sort_order)
VALUES
    ('Presidente', 'Representante principal del CEE.', 1),
    ('Tesorero', 'Responsable de finanzas.', 2),
    ('Secretario', 'Responsable de actas y documentos.', 3),
    ('Directiva', 'Integrante general de directiva.', 4)
ON CONFLICT (name) DO UPDATE
SET
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order,
    updated_at = now();

INSERT INTO publication_categories (name, slug, description, is_active)
VALUES
    ('General', 'general', 'Publicaciones generales.', TRUE),
    ('Academico', 'academico', 'Informacion academica.', TRUE),
    ('Comunidad', 'comunidad', 'Vida universitaria y comunidad.', TRUE)
ON CONFLICT (slug) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    updated_at = now();

INSERT INTO event_categories (name, slug, description, is_active)
VALUES
    ('Academico', 'academico', 'Charlas, talleres y actividades academicas.', TRUE),
    ('Bienestar', 'bienestar', 'Actividades de bienestar estudiantil.', TRUE),
    ('Comunidad', 'comunidad', 'Actividades de comunidad.', TRUE)
ON CONFLICT (slug) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    updated_at = now();

INSERT INTO request_categories (name, slug, description, is_active)
VALUES
    ('Academica', 'academica', 'Solicitudes academicas.', TRUE),
    ('Bienestar', 'bienestar', 'Solicitudes de bienestar estudiantil.', TRUE),
    ('Infraestructura', 'infraestructura', 'Solicitudes sobre espacios y recursos.', TRUE),
    ('Financiera', 'financiera', 'Solicitudes relacionadas con apoyo financiero.', TRUE)
ON CONFLICT (slug) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    updated_at = now();

INSERT INTO expense_categories (name, slug, description, is_active)
VALUES
    ('Operacional', 'operacional', 'Gastos operacionales del CEE.', TRUE),
    ('Evento', 'evento', 'Gastos asociados a eventos.', TRUE),
    ('Materiales', 'materiales', 'Compra de materiales e insumos.', TRUE),
    ('Transparencia', 'transparencia', 'Gastos asociados a publicacion y rendicion.', TRUE)
ON CONFLICT (slug) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    updated_at = now();

INSERT INTO inventory_categories (name, slug, description, is_active)
VALUES
    ('Equipamiento', 'equipamiento', 'Equipos prestables o de uso interno.', TRUE),
    ('Materiales', 'materiales', 'Materiales inventariables.', TRUE),
    ('Espacios', 'espacios', 'Recursos asociados a espacios.', TRUE)
ON CONFLICT (slug) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    updated_at = now();

INSERT INTO document_categories (name, slug, description, is_active)
VALUES
    ('Actas', 'actas', 'Actas y registros de reuniones.', TRUE),
    ('Finanzas', 'finanzas', 'Documentos de presupuesto, ingresos y gastos.', TRUE),
    ('Normativa', 'normativa', 'Reglamentos y documentos normativos.', TRUE),
    ('Transparencia', 'transparencia', 'Documentos publicos de transparencia.', TRUE)
ON CONFLICT (slug) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    updated_at = now();

COMMIT;
