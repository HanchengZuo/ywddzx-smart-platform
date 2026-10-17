"""Retire removed page switches without deleting historical business data."""
from alembic import op

revision = '20261017_002'
down_revision = '20261017_001'
branch_labels = None
depends_on = None


def upgrade():
    keys = ['view_peer_reviews', 'manage_peer_review_tasks', 'view_training',
            'view_training_materials', 'upload_training_materials']
    with op.get_bind().connection.cursor() as cur:
        for table in ('user_permissions', 'role_permissions'):
            cur.execute(f'DELETE FROM {table} WHERE permission_key = ANY(%s)', (keys,))
        cur.execute('DELETE FROM system_page_visibility WHERE page_key = ANY(%s)',
                    (['/assessment/peer-review', '/training', '/training/materials'],))


def downgrade():
    # Do not invent historical grants for retired pages.
    pass
