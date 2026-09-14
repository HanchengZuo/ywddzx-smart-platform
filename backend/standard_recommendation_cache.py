"""Bounded, short-lived reuse of successful recommendations for unchanged evidence."""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
from threading import Lock
import time

MAX_ENTRIES = 64
TTL_SECONDS = 1800
_entries = OrderedDict()
_lock = Lock()


def recommendation_key(description, standards, history):
    # Include the entire caller-visible evidence, not merely the description.
    # Changed permissions, reference edits, audit decisions or catalog disablement
    # must invalidate reuse. Store only the digest, never a second copy of history.
    payload = [str(description or '').strip(),
               sorted(standards, key=lambda row: str(row['standard_id'])), sorted(history)]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), default=str).encode()).hexdigest()


def get_recommendation(key):
    with _lock:
        entry = _entries.get(key)
        if entry is None:
            return None
        expires, result = entry
        if expires <= time.monotonic():
            del _entries[key]
            return None
        _entries.move_to_end(key)
        return deepcopy(result)


def remember_recommendation(key, result):
    if not result.get('generated'):
        return
    with _lock:
        _entries[key] = (time.monotonic()+TTL_SECONDS, deepcopy(result))
        _entries.move_to_end(key)
        while len(_entries) > MAX_ENTRIES:
            _entries.popitem(last=False)
