-- CEE Conecta - PostgreSQL base schema
-- Agent: agent.database_designer
-- Date: 2026-06-21

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    CREATE TYPE user_status AS ENUM ('ACTIVE', 'INACTIVE', 'SUSPENDED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE publication_status AS ENUM ('DRAFT', 'PUBLISHED', 'ARCHIVED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE event_status AS ENUM ('PLANNED', 'PUBLISHED', 'FINISHED', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE request_status AS ENUM ('SUBMITTED', 'IN_REVIEW', 'OBSERVED', 'APPROVED', 'REJECTED', 'CLOSED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE request_priority AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'URGENT');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE meeting_status AS ENUM ('SCHEDULED', 'DONE', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE agreement_status AS ENUM ('OPEN', 'IN_PROGRESS', 'DONE', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE budget_status AS ENUM ('DRAFT', 'ACTIVE', 'CLOSED', 'ARCHIVED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE financial_record_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'VOID');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE resource_status AS ENUM ('AVAILABLE', 'LOANED', 'DAMAGED', 'LOST', 'RETIRED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE inventory_movement_type AS ENUM ('IN', 'OUT', 'ADJUSTMENT', 'LOAN', 'RETURN');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE loan_status AS ENUM ('REQUESTED', 'APPROVED', 'LOANED', 'RETURNED', 'CANCELLED', 'OVERDUE');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE document_status AS ENUM ('DRAFT', 'PUBLISHED', 'ARCHIVED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE survey_status AS ENUM ('DRAFT', 'OPEN', 'CLOSED', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE question_type AS ENUM ('TEXT', 'SINGLE_CHOICE', 'MULTIPLE_CHOICE', 'RATING');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE voting_status AS ENUM ('DRAFT', 'OPEN', 'CLOSED', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE notification_status AS ENUM ('PENDING', 'SENT', 'READ', 'FAILED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Security and users

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(320) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    status user_status NOT NULL DEFAULT 'ACTIVE',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT users_email_format_chk CHECK (position('@' IN email) > 1),
    CONSTRAINT users_name_not_blank_chk CHECK (char_length(btrim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT roles_name_upper_chk CHECK (name = upper(name)),
    CONSTRAINT roles_name_not_blank_chk CHECK (char_length(btrim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(120) NOT NULL UNIQUE,
    module VARCHAR(80) NOT NULL,
    action VARCHAR(80) NOT NULL,
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT permissions_code_not_blank_chk CHECK (char_length(btrim(code)) > 0),
    CONSTRAINT permissions_module_action_unique UNIQUE (module, action)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT role_permissions_unique UNIQUE (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT user_roles_unique_active UNIQUE (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(40) NOT NULL DEFAULT 'GOOGLE',
    session_token_hash TEXT NOT NULL UNIQUE,
    ip_address INET,
    user_agent TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sessions_provider_chk CHECK (provider IN ('GOOGLE')),
    CONSTRAINT sessions_expires_after_start_chk CHECK (expires_at > started_at)
);

CREATE TABLE IF NOT EXISTS auth_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    email VARCHAR(320),
    event_type VARCHAR(80) NOT NULL,
    provider VARCHAR(40) NOT NULL DEFAULT 'GOOGLE',
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    error_code VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT auth_events_type_chk CHECK (event_type IN ('LOGIN_SUCCESS', 'LOGIN_FAILURE', 'LOGOUT', 'SESSION_REVOKED')),
    CONSTRAINT auth_events_provider_chk CHECK (provider IN ('GOOGLE'))
);

-- Student center

CREATE TABLE IF NOT EXISTS student_centers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(180) NOT NULL,
    slug VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    institutional_email VARCHAR(320),
    website_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT student_centers_name_not_blank_chk CHECK (char_length(btrim(name)) > 0),
    CONSTRAINT student_centers_slug_not_blank_chk CHECK (char_length(btrim(slug)) > 0)
);

CREATE TABLE IF NOT EXISTS board_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_center_id UUID NOT NULL REFERENCES student_centers(id) ON DELETE RESTRICT,
    name VARCHAR(180) NOT NULL,
    starts_on DATE NOT NULL,
    ends_on DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT board_periods_dates_chk CHECK (ends_on IS NULL OR ends_on > starts_on)
);

CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT positions_name_not_blank_chk CHECK (char_length(btrim(name)) > 0),
    CONSTRAINT positions_sort_order_chk CHECK (sort_order >= 0)
);

CREATE TABLE IF NOT EXISTS board_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_period_id UUID NOT NULL REFERENCES board_periods(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    position_id UUID NOT NULL REFERENCES positions(id) ON DELETE RESTRICT,
    appointed_on DATE NOT NULL,
    ended_on DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT board_members_dates_chk CHECK (ended_on IS NULL OR ended_on >= appointed_on),
    CONSTRAINT board_members_unique_period_user_position UNIQUE (board_period_id, user_id, position_id)
);

-- Publications

CREATE TABLE IF NOT EXISTS publication_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT publication_categories_name_not_blank_chk CHECK (char_length(btrim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS news (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(220) NOT NULL,
    slug VARCHAR(240) NOT NULL UNIQUE,
    summary TEXT,
    content TEXT NOT NULL,
    author_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    category_id UUID REFERENCES publication_categories(id) ON DELETE SET NULL,
    status publication_status NOT NULL DEFAULT 'DRAFT',
    published_at TIMESTAMPTZ,
    image_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT news_title_not_blank_chk CHECK (char_length(btrim(title)) > 0),
    CONSTRAINT news_content_not_blank_chk CHECK (char_length(btrim(content)) > 0),
    CONSTRAINT news_published_at_chk CHECK (status <> 'PUBLISHED' OR published_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS announcements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(220) NOT NULL,
    slug VARCHAR(240) NOT NULL UNIQUE,
    summary TEXT,
    content TEXT NOT NULL,
    author_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    category_id UUID REFERENCES publication_categories(id) ON DELETE SET NULL,
    status publication_status NOT NULL DEFAULT 'DRAFT',
    priority INTEGER NOT NULL DEFAULT 3,
    published_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT announcements_title_not_blank_chk CHECK (char_length(btrim(title)) > 0),
    CONSTRAINT announcements_content_not_blank_chk CHECK (char_length(btrim(content)) > 0),
    CONSTRAINT announcements_priority_chk CHECK (priority BETWEEN 1 AND 5),
    CONSTRAINT announcements_published_at_chk CHECK (status <> 'PUBLISHED' OR published_at IS NOT NULL),
    CONSTRAINT announcements_expiration_chk CHECK (expires_at IS NULL OR published_at IS NULL OR expires_at > published_at)
);

CREATE TABLE IF NOT EXISTS publication_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    news_id UUID REFERENCES news(id) ON DELETE CASCADE,
    announcement_id UUID REFERENCES announcements(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_url TEXT NOT NULL,
    mime_type VARCHAR(120) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT publication_attachments_owner_chk CHECK (
        ((news_id IS NOT NULL)::integer + (announcement_id IS NOT NULL)::integer) = 1
    ),
    CONSTRAINT publication_attachments_file_size_chk CHECK (file_size_bytes > 0)
);

-- Events

CREATE TABLE IF NOT EXISTS event_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT event_categories_name_not_blank_chk CHECK (char_length(btrim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES event_categories(id) ON DELETE SET NULL,
    name VARCHAR(220) NOT NULL,
    description TEXT,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    location VARCHAR(255),
    capacity INTEGER,
    responsible_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status event_status NOT NULL DEFAULT 'PLANNED',
    published_at TIMESTAMPTZ,
    image_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT events_name_not_blank_chk CHECK (char_length(btrim(name)) > 0),
    CONSTRAINT events_dates_chk CHECK (ends_at > starts_at),
    CONSTRAINT events_capacity_chk CHECK (capacity IS NULL OR capacity > 0),
    CONSTRAINT events_published_at_chk CHECK (status <> 'PUBLISHED' OR published_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS event_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(30) NOT NULL DEFAULT 'REGISTERED',
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT event_registrations_unique UNIQUE (event_id, user_id),
    CONSTRAINT event_registrations_status_chk CHECK (status IN ('REGISTERED', 'WAITLISTED', 'CANCELLED')),
    CONSTRAINT event_registrations_cancelled_at_chk CHECK (status <> 'CANCELLED' OR cancelled_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS event_attendance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    checked_in_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_by UUID REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT event_attendance_unique UNIQUE (event_id, user_id)
);

-- Requests

CREATE TABLE IF NOT EXISTS request_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT request_categories_name_not_blank_chk CHECK (char_length(btrim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    category_id UUID REFERENCES request_categories(id) ON DELETE SET NULL,
    title VARCHAR(220) NOT NULL,
    description TEXT NOT NULL,
    status request_status NOT NULL DEFAULT 'SUBMITTED',
    priority request_priority NOT NULL DEFAULT 'MEDIUM',
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    resolution TEXT,
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT requests_title_not_blank_chk CHECK (char_length(btrim(title)) > 0),
    CONSTRAINT requests_description_not_blank_chk CHECK (char_length(btrim(description)) > 0),
    CONSTRAINT requests_closed_at_chk CHECK (status <> 'CLOSED' OR closed_at IS NOT NULL),
    CONSTRAINT requests_resolved_at_chk CHECK (status NOT IN ('APPROVED', 'REJECTED') OR resolved_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS request_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    old_status request_status,
    new_status request_status NOT NULL,
    changed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT request_status_history_change_chk CHECK (old_status IS NULL OR old_status <> new_status)
);

CREATE TABLE IF NOT EXISTS request_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    author_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    body TEXT NOT NULL,
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT request_comments_body_not_blank_chk CHECK (char_length(btrim(body)) > 0)
);

CREATE TABLE IF NOT EXISTS request_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_url TEXT NOT NULL,
    mime_type VARCHAR(120) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT request_attachments_file_size_chk CHECK (file_size_bytes > 0)
);

-- Meetings

CREATE TABLE IF NOT EXISTS meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_period_id UUID REFERENCES board_periods(id) ON DELETE SET NULL,
    title VARCHAR(220) NOT NULL,
    description TEXT,
    scheduled_at TIMESTAMPTZ NOT NULL,
    location VARCHAR(255),
    status meeting_status NOT NULL DEFAULT 'SCHEDULED',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT meetings_title_not_blank_chk CHECK (char_length(btrim(title)) > 0)
);

CREATE TABLE IF NOT EXISTS meeting_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_text VARCHAR(120),
    attended BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT meeting_participants_unique UNIQUE (meeting_id, user_id)
);

CREATE TABLE IF NOT EXISTS meeting_minutes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID NOT NULL UNIQUE REFERENCES meetings(id) ON DELETE CASCADE,
    summary TEXT,
    body TEXT NOT NULL,
    approved_at TIMESTAMPTZ,
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT meeting_minutes_body_not_blank_chk CHECK (char_length(btrim(body)) > 0)
);

CREATE TABLE IF NOT EXISTS agreements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
    title VARCHAR(220) NOT NULL,
    description TEXT,
    status agreement_status NOT NULL DEFAULT 'OPEN',
    responsible_id UUID REFERENCES users(id) ON DELETE SET NULL,
    due_on DATE,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT agreements_title_not_blank_chk CHECK (char_length(btrim(title)) > 0),
    CONSTRAINT agreements_completed_at_chk CHECK (status <> 'DONE' OR completed_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS agreement_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agreement_id UUID NOT NULL REFERENCES agreements(id) ON DELETE CASCADE,
    title VARCHAR(220) NOT NULL,
    description TEXT,
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    due_on DATE,
    status agreement_status NOT NULL DEFAULT 'OPEN',
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT agreement_tasks_title_not_blank_chk CHECK (char_length(btrim(title)) > 0),
    CONSTRAINT agreement_tasks_completed_at_chk CHECK (status <> 'DONE' OR completed_at IS NOT NULL)
);

-- Finances

CREATE TABLE IF NOT EXISTS budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_center_id UUID REFERENCES student_centers(id) ON DELETE SET NULL,
    name VARCHAR(180) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    status budget_status NOT NULL DEFAULT 'DRAFT',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT budgets_name_not_blank_chk CHECK (char_length(btrim(name)) > 0),
    CONSTRAINT budgets_dates_chk CHECK (period_end >= period_start),
    CONSTRAINT budgets_total_amount_chk CHECK (total_amount >= 0)
);

CREATE TABLE IF NOT EXISTS budget_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id UUID NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    name VARCHAR(180) NOT NULL,
    description TEXT,
    planned_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    spent_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT budget_items_name_not_blank_chk CHECK (char_length(btrim(name)) > 0),
    CONSTRAINT budget_items_planned_amount_chk CHECK (planned_amount >= 0),
    CONSTRAINT budget_items_spent_amount_chk CHECK (spent_amount >= 0)
);

CREATE TABLE IF NOT EXISTS income_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id UUID REFERENCES budgets(id) ON DELETE SET NULL,
    amount NUMERIC(14, 2) NOT NULL,
    source VARCHAR(180) NOT NULL,
    description TEXT,
    received_on DATE NOT NULL,
    recorded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    status financial_record_status NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT income_records_amount_chk CHECK (amount > 0),
    CONSTRAINT income_records_source_not_blank_chk CHECK (char_length(btrim(source)) > 0)
);

CREATE TABLE IF NOT EXISTS expense_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT expense_categories_name_not_blank_chk CHECK (char_length(btrim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS expense_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id UUID REFERENCES budgets(id) ON DELETE SET NULL,
    category_id UUID REFERENCES expense_categories(id) ON DELETE SET NULL,
    amount NUMERIC(14, 2) NOT NULL,
    description TEXT NOT NULL,
    spent_on DATE NOT NULL,
    responsible_id UUID REFERENCES users(id) ON DELETE SET NULL,
    receipt_url TEXT NOT NULL,
    status financial_record_status NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT expense_records_amount_chk CHECK (amount > 0),
    CONSTRAINT expense_records_description_not_blank_chk CHECK (char_length(btrim(description)) > 0),
    CONSTRAINT expense_records_receipt_not_blank_chk CHECK (char_length(btrim(receipt_url)) > 0)
);

CREATE TABLE IF NOT EXISTS financial_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id UUID REFERENCES budgets(id) ON DELETE SET NULL,
    income_record_id UUID REFERENCES income_records(id) ON DELETE CASCADE,
    expense_record_id UUID REFERENCES expense_records(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_url TEXT NOT NULL,
    mime_type VARCHAR(120) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT financial_documents_owner_chk CHECK (
        ((income_record_id IS NOT NULL)::integer + (expense_record_id IS NOT NULL)::integer) = 1
    ),
    CONSTRAINT financial_documents_file_size_chk CHECK (file_size_bytes > 0)
);

-- Inventory

CREATE TABLE IF NOT EXISTS inventory_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT inventory_categories_name_not_blank_chk CHECK (char_length(btrim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS inventory_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES inventory_categories(id) ON DELETE SET NULL,
    name VARCHAR(180) NOT NULL,
    code VARCHAR(80) NOT NULL UNIQUE,
    description TEXT,
    status resource_status NOT NULL DEFAULT 'AVAILABLE',
    quantity INTEGER NOT NULL DEFAULT 1,
    location VARCHAR(180),
    acquired_on DATE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT inventory_items_name_not_blank_chk CHECK (char_length(btrim(name)) > 0),
    CONSTRAINT inventory_items_code_not_blank_chk CHECK (char_length(btrim(code)) > 0),
    CONSTRAINT inventory_items_quantity_chk CHECK (quantity >= 0)
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
    movement_type inventory_movement_type NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    from_status resource_status,
    to_status resource_status,
    reason TEXT,
    performed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT inventory_movements_quantity_chk CHECK (quantity > 0)
);

CREATE TABLE IF NOT EXISTS resource_loans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    borrower_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    loaned_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    returned_at TIMESTAMPTZ,
    status loan_status NOT NULL DEFAULT 'REQUESTED',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT resource_loans_due_chk CHECK (due_at IS NULL OR loaned_at IS NULL OR due_at > loaned_at),
    CONSTRAINT resource_loans_returned_chk CHECK (returned_at IS NULL OR loaned_at IS NULL OR returned_at >= loaned_at)
);

CREATE TABLE IF NOT EXISTS resource_returns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL UNIQUE REFERENCES resource_loans(id) ON DELETE CASCADE,
    returned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    received_by UUID REFERENCES users(id) ON DELETE SET NULL,
    item_status resource_status NOT NULL DEFAULT 'AVAILABLE',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Documents

CREATE TABLE IF NOT EXISTS document_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT document_categories_name_not_blank_chk CHECK (char_length(btrim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES document_categories(id) ON DELETE SET NULL,
    title VARCHAR(220) NOT NULL,
    description TEXT,
    visibility VARCHAR(30) NOT NULL DEFAULT 'PUBLIC',
    status document_status NOT NULL DEFAULT 'DRAFT',
    owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT documents_title_not_blank_chk CHECK (char_length(btrim(title)) > 0),
    CONSTRAINT documents_visibility_chk CHECK (visibility IN ('PUBLIC', 'AUTHENTICATED', 'BOARD', 'PRIVATE')),
    CONSTRAINT documents_published_at_chk CHECK (status <> 'PUBLISHED' OR published_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_url TEXT NOT NULL,
    mime_type VARCHAR(120) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    changelog TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT document_versions_unique UNIQUE (document_id, version_number),
    CONSTRAINT document_versions_version_chk CHECK (version_number >= 1),
    CONSTRAINT document_versions_file_size_chk CHECK (file_size_bytes > 0)
);

-- Participation

CREATE TABLE IF NOT EXISTS surveys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(220) NOT NULL,
    description TEXT,
    opens_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ,
    status survey_status NOT NULL DEFAULT 'DRAFT',
    is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT surveys_title_not_blank_chk CHECK (char_length(btrim(title)) > 0),
    CONSTRAINT surveys_dates_chk CHECK (opens_at IS NULL OR closes_at IS NULL OR closes_at > opens_at)
);

CREATE TABLE IF NOT EXISTS survey_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_id UUID NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_type question_type NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT survey_questions_text_not_blank_chk CHECK (char_length(btrim(question_text)) > 0),
    CONSTRAINT survey_questions_sort_order_chk CHECK (sort_order >= 0)
);

CREATE TABLE IF NOT EXISTS survey_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id UUID NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT survey_options_text_not_blank_chk CHECK (char_length(btrim(option_text)) > 0),
    CONSTRAINT survey_options_sort_order_chk CHECK (sort_order >= 0)
);

CREATE TABLE IF NOT EXISTS survey_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_id UUID NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
    option_id UUID REFERENCES survey_options(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    text_answer TEXT,
    numeric_answer NUMERIC(8, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT survey_responses_answer_chk CHECK (
        option_id IS NOT NULL OR text_answer IS NOT NULL OR numeric_answer IS NOT NULL
    )
);

CREATE TABLE IF NOT EXISTS votings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(220) NOT NULL,
    description TEXT,
    opens_at TIMESTAMPTZ NOT NULL,
    closes_at TIMESTAMPTZ NOT NULL,
    status voting_status NOT NULL DEFAULT 'DRAFT',
    is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT votings_title_not_blank_chk CHECK (char_length(btrim(title)) > 0),
    CONSTRAINT votings_dates_chk CHECK (closes_at > opens_at)
);

CREATE TABLE IF NOT EXISTS voting_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    voting_id UUID NOT NULL REFERENCES votings(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT voting_options_text_not_blank_chk CHECK (char_length(btrim(option_text)) > 0),
    CONSTRAINT voting_options_sort_order_chk CHECK (sort_order >= 0),
    CONSTRAINT voting_options_voting_id_id_unique UNIQUE (voting_id, id)
);

CREATE TABLE IF NOT EXISTS eligible_voters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    voting_id UUID NOT NULL REFERENCES votings(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT eligible_voters_unique UNIQUE (voting_id, user_id),
    CONSTRAINT eligible_voters_voting_id_id_unique UNIQUE (voting_id, id)
);

CREATE TABLE IF NOT EXISTS votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    voting_id UUID NOT NULL REFERENCES votings(id) ON DELETE CASCADE,
    option_id UUID NOT NULL,
    eligible_voter_id UUID NOT NULL,
    cast_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT votes_option_fk FOREIGN KEY (voting_id, option_id)
        REFERENCES voting_options(voting_id, id) ON DELETE CASCADE,
    CONSTRAINT votes_eligible_voter_fk FOREIGN KEY (voting_id, eligible_voter_id)
        REFERENCES eligible_voters(voting_id, id) ON DELETE CASCADE,
    CONSTRAINT votes_unique_voter UNIQUE (voting_id, eligible_voter_id)
);

-- System

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(120) NOT NULL,
    entity_type VARCHAR(120) NOT NULL,
    entity_id UUID,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT audit_events_action_not_blank_chk CHECK (char_length(btrim(action)) > 0),
    CONSTRAINT audit_events_entity_type_not_blank_chk CHECK (char_length(btrim(entity_type)) > 0)
);

CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(180) NOT NULL,
    body TEXT NOT NULL,
    status notification_status NOT NULL DEFAULT 'PENDING',
    sent_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT notifications_title_not_blank_chk CHECK (char_length(btrim(title)) > 0),
    CONSTRAINT notifications_body_not_blank_chk CHECK (char_length(btrim(body)) > 0),
    CONSTRAINT notifications_read_at_chk CHECK (status <> 'READ' OR read_at IS NOT NULL)
);

-- Important indexes

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_events_user_id ON auth_events(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_events_created_at ON auth_events(created_at);

CREATE INDEX IF NOT EXISTS idx_board_periods_student_center_id ON board_periods(student_center_id);
CREATE INDEX IF NOT EXISTS idx_board_members_user_id ON board_members(user_id);
CREATE INDEX IF NOT EXISTS idx_board_members_period_id ON board_members(board_period_id);

CREATE INDEX IF NOT EXISTS idx_news_status_published_at ON news(status, published_at);
CREATE INDEX IF NOT EXISTS idx_news_author_id ON news(author_id);
CREATE INDEX IF NOT EXISTS idx_news_category_id ON news(category_id);
CREATE INDEX IF NOT EXISTS idx_announcements_status_published_at ON announcements(status, published_at);
CREATE INDEX IF NOT EXISTS idx_announcements_category_id ON announcements(category_id);

CREATE INDEX IF NOT EXISTS idx_events_status_starts_at ON events(status, starts_at);
CREATE INDEX IF NOT EXISTS idx_events_category_id ON events(category_id);
CREATE INDEX IF NOT EXISTS idx_event_registrations_user_id ON event_registrations(user_id);
CREATE INDEX IF NOT EXISTS idx_event_registrations_event_id ON event_registrations(event_id);
CREATE INDEX IF NOT EXISTS idx_event_attendance_event_id ON event_attendance(event_id);

CREATE INDEX IF NOT EXISTS idx_requests_requester_id ON requests(requester_id);
CREATE INDEX IF NOT EXISTS idx_requests_assigned_to ON requests(assigned_to);
CREATE INDEX IF NOT EXISTS idx_requests_status_created_at ON requests(status, created_at);
CREATE INDEX IF NOT EXISTS idx_requests_category_id ON requests(category_id);
CREATE INDEX IF NOT EXISTS idx_request_status_history_request_id ON request_status_history(request_id);
CREATE INDEX IF NOT EXISTS idx_request_comments_request_id ON request_comments(request_id);

CREATE INDEX IF NOT EXISTS idx_meetings_scheduled_at ON meetings(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_meeting_participants_meeting_id ON meeting_participants(meeting_id);
CREATE INDEX IF NOT EXISTS idx_agreements_status_due_on ON agreements(status, due_on);
CREATE INDEX IF NOT EXISTS idx_agreement_tasks_agreement_id ON agreement_tasks(agreement_id);

CREATE INDEX IF NOT EXISTS idx_budgets_period ON budgets(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_budget_items_budget_id ON budget_items(budget_id);
CREATE INDEX IF NOT EXISTS idx_income_records_budget_id ON income_records(budget_id);
CREATE INDEX IF NOT EXISTS idx_income_records_received_on ON income_records(received_on);
CREATE INDEX IF NOT EXISTS idx_expense_records_budget_id ON expense_records(budget_id);
CREATE INDEX IF NOT EXISTS idx_expense_records_category_id ON expense_records(category_id);
CREATE INDEX IF NOT EXISTS idx_expense_records_spent_on ON expense_records(spent_on);

CREATE INDEX IF NOT EXISTS idx_inventory_items_category_id ON inventory_items(category_id);
CREATE INDEX IF NOT EXISTS idx_inventory_items_status ON inventory_items(status);
CREATE INDEX IF NOT EXISTS idx_inventory_movements_item_id ON inventory_movements(item_id);
CREATE INDEX IF NOT EXISTS idx_resource_loans_item_id ON resource_loans(item_id);
CREATE INDEX IF NOT EXISTS idx_resource_loans_borrower_id ON resource_loans(borrower_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_resource_loans_one_active_per_item
    ON resource_loans(item_id)
    WHERE status IN ('APPROVED', 'LOANED', 'OVERDUE') AND deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_documents_status_published_at ON documents(status, published_at);
CREATE INDEX IF NOT EXISTS idx_documents_category_id ON documents(category_id);
CREATE INDEX IF NOT EXISTS idx_document_versions_document_id ON document_versions(document_id);

CREATE INDEX IF NOT EXISTS idx_surveys_status ON surveys(status);
CREATE INDEX IF NOT EXISTS idx_survey_questions_survey_id ON survey_questions(survey_id);
CREATE INDEX IF NOT EXISTS idx_survey_options_question_id ON survey_options(question_id);
CREATE INDEX IF NOT EXISTS idx_survey_responses_survey_id ON survey_responses(survey_id);
CREATE INDEX IF NOT EXISTS idx_survey_responses_user_id ON survey_responses(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_survey_responses_one_free_answer
    ON survey_responses(question_id, user_id)
    WHERE option_id IS NULL AND user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_survey_responses_one_option_answer
    ON survey_responses(question_id, user_id, option_id)
    WHERE option_id IS NOT NULL AND user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_votings_status_dates ON votings(status, opens_at, closes_at);
CREATE INDEX IF NOT EXISTS idx_voting_options_voting_id ON voting_options(voting_id);
CREATE INDEX IF NOT EXISTS idx_eligible_voters_user_id ON eligible_voters(user_id);
CREATE INDEX IF NOT EXISTS idx_votes_voting_id ON votes(voting_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_actor_id ON audit_events(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_entity ON audit_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_events_metadata ON audit_events USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_notifications_user_status ON notifications(user_id, status);
