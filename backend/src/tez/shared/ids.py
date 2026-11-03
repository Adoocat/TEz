"""UUIDv7 identifiers (RFC 9562), as text.

Python 3.12 has no `uuid.uuid7` (3.14 adds it). Ids embed a millisecond timestamp, so they
sort by creation time; within one millisecond the 12-bit `rand_a` field is a counter
(RFC 9562 method 1), so ids made by one process are strictly increasing.
"""

import secrets
import threading
import time
import uuid

_lock = threading.Lock()
_last_ms = 0
_counter = 0
_COUNTER_MAX = 0xFFF


def new_id() -> str:
    global _last_ms, _counter
    with _lock:
        now_ms = time.time_ns() // 1_000_000
        if now_ms > _last_ms:
            _last_ms = now_ms
            # Start low and random so ids stay unguessable but leave room to count up.
            _counter = secrets.randbits(10)
        else:
            # Same millisecond, or the clock stepped back: keep counting from the last id.
            _counter += 1
            if _counter > _COUNTER_MAX:
                _last_ms += 1
                _counter = 0
        ms, counter = _last_ms, _counter
    value = (
        (ms & 0xFFFF_FFFF_FFFF) << 80
        | 0x7 << 76  # version
        | counter << 64
        | 0b10 << 62  # RFC variant
        | secrets.randbits(62)
    )
    return str(uuid.UUID(int=value))
