"""Print an import/route contract without connecting, starting jobs or spawning commands."""
import importlib
import json
import sys
from unittest.mock import patch


def forbidden(*args, **kwargs):
    raise AssertionError('Import attempted external I/O or started a background task')


if __name__ == '__main__':
    with patch('psycopg2.connect', side_effect=forbidden), \
         patch('socket.socket.connect', side_effect=forbidden), \
         patch('threading.Thread.start', side_effect=forbidden), \
         patch('subprocess.Popen', side_effect=forbidden):
        core = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else 'app')
    print(json.dumps({
        'routes': sorted((r.rule, r.endpoint, sorted(r.methods)) for r in core.app.url_map.iter_rules()),
        'before_request': [f.__name__ for f in core.app.before_request_funcs.get(None, [])],
        'after_request': [f.__name__ for f in core.app.after_request_funcs.get(None, [])],
        'extensions': sorted(core.app.extensions),
        'request_class': core.app.request_class.__name__,
        'backup_scheduler_started': core.backup_scheduler_started,
        'limits': {k: core.app.config[k] for k in ('MAX_CONTENT_LENGTH', 'MAX_FORM_MEMORY_SIZE', 'MAX_FORM_PARTS')},
    }, ensure_ascii=False))
