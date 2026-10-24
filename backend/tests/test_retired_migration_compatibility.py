from pathlib import Path
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory


class RetiredMigrationCompatibilityTests(unittest.TestCase):
    def setUp(self):
        config = Config()
        config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
        self.scripts = ScriptDirectory.from_config(config)

    def test_database_with_retired_revision_can_reach_the_current_single_head(self):
        revision = self.scripts.get_revision('20261024_001')
        self.assertEqual(revision.down_revision, '20261023_001')
        self.assertEqual(self.scripts.get_heads(), ['20261025_001'])
        steps = list(self.scripts.iterate_revisions('heads', '20261024_001'))
        self.assertEqual([step.revision for step in steps], ['20261025_001'])

    def test_compatibility_marker_never_recreates_or_deletes_retired_tables(self):
        migration = self.scripts.get_revision('20261024_001').module
        # Both functions must remain usable without an Alembic operation/database context.
        self.assertIsNone(migration.upgrade())
        self.assertIsNone(migration.downgrade())
