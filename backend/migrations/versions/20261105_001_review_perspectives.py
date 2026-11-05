"""Retire the oil/gas template's obsolete odor checklist bindings, with audit."""
from alembic import op

revision = '20261105_001'
down_revision = '20261103_002'
branch_labels = depends_on = None


def upgrade():
    # The deleted rows and their audit are one statement in the migration transaction.
    op.execute("""
        WITH removed AS (
            DELETE FROM role_inspection_table_scopes AS scope
            USING inspection_tables AS checklist
            WHERE scope.role = 'oil_gas'
              AND scope.inspection_table_id = checklist.id
              AND checklist.checklist_mode = 'offline'
              AND btrim(checklist.table_name) IN (
                  '环境无异味管理检查表', '环境无异味管理检查表（现场）',
                  '环境无异味管理检查表(现场)'
              )
            RETURNING scope.*
        )
        INSERT INTO security_audit_logs (
            actor_username, actor_role, action_type, action_result,
            affected_count, details, created_at
        )
        SELECT 'SYSTEM', 'system', 'oil_gas_odor_scope_migrated', 'success',
               count(*)::integer,
               jsonb_build_object('revision', '20261105_001',
                   'removed_scopes', jsonb_agg(to_jsonb(removed))), CURRENT_TIMESTAMP
        FROM removed HAVING count(*) > 0
    """)


def downgrade():
    pass  # Keep the ownership correction and the recoverable audit of prior bindings.
