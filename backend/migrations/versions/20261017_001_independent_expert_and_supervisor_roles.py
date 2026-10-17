"""Separate expert access and initialize the supervisor management template."""
from alembic import op
from role_permission_transition import split_permission_templates

revision = '20261017_001'
down_revision = '20261016_001'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_bind().connection.cursor() as cur:
        split_permission_templates(cur)


def downgrade():
    raise RuntimeError('角色拆分后可能已有独立配置；请先人工合并权限与账号，再回退此迁移。')
