-- assessment peer reviews: 成员互评模板、任务和评价结果

CREATE TABLE peer_review_templates (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    default_deadline_at TIMESTAMP,
    show_participation BOOLEAN NOT NULL DEFAULT TRUE,
    show_reviewer BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE peer_review_template_items (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES peer_review_templates(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL DEFAULT 'score',
    title TEXT NOT NULL,
    description TEXT,
    max_score INTEGER NOT NULL DEFAULT 5,
    sort_order INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE peer_review_template_participants (
    template_id INTEGER NOT NULL REFERENCES peer_review_templates(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (template_id, user_id)
);

CREATE TABLE peer_review_template_reviewees (
    template_id INTEGER NOT NULL REFERENCES peer_review_templates(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (template_id, user_id)
);

CREATE TABLE peer_review_tasks (
    id SERIAL PRIMARY KEY,
    template_id INTEGER REFERENCES peer_review_templates(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    deadline_at TIMESTAMP,
    show_participation BOOLEAN NOT NULL DEFAULT TRUE,
    show_reviewer BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'active',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE peer_review_task_items (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES peer_review_tasks(id) ON DELETE CASCADE,
    source_template_item_id INTEGER REFERENCES peer_review_template_items(id) ON DELETE SET NULL,
    item_type TEXT NOT NULL DEFAULT 'score',
    title TEXT NOT NULL,
    description TEXT,
    max_score INTEGER NOT NULL DEFAULT 5,
    sort_order INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE peer_review_task_participants (
    task_id INTEGER NOT NULL REFERENCES peer_review_tasks(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, user_id)
);

CREATE TABLE peer_review_task_reviewees (
    task_id INTEGER NOT NULL REFERENCES peer_review_tasks(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, user_id)
);

CREATE TABLE peer_review_responses (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES peer_review_tasks(id) ON DELETE CASCADE,
    reviewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reviewee_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (task_id, reviewer_id, reviewee_id)
);

CREATE TABLE peer_review_response_items (
    id SERIAL PRIMARY KEY,
    response_id INTEGER NOT NULL REFERENCES peer_review_responses(id) ON DELETE CASCADE,
    task_item_id INTEGER NOT NULL REFERENCES peer_review_task_items(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL DEFAULT 'score',
    score_value INTEGER,
    text_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (response_id, task_item_id)
);

CREATE INDEX idx_peer_review_tasks_status_deadline ON peer_review_tasks (status, deadline_at);
CREATE INDEX idx_peer_review_responses_task_reviewer ON peer_review_responses (task_id, reviewer_id);
CREATE INDEX idx_peer_review_responses_task_reviewee ON peer_review_responses (task_id, reviewee_id);
