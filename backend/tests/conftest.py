"""Isolate the test suite from the developer's real database and media directory.

Without this, running pytest writes into backend/.local: every upload test leaves a
real match row and a real media file behind. That is how an orphaned match ended up
stuck at status='processing' in the live database.

backend/src/config.py reads these variables at IMPORT time, so they must be set
before anything under backend.src is imported. conftest is imported before test
modules, which makes this the right place.
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="aifp-tests-")
os.environ.setdefault("AIFP_DATA_DIR", _TMP)
os.environ.setdefault("AIFP_MEDIA_DIR", os.path.join(_TMP, "media"))
os.environ.setdefault("AIFP_DB_PATH", os.path.join(_TMP, "veo.db"))
os.makedirs(os.environ["AIFP_MEDIA_DIR"], exist_ok=True)
