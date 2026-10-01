"""Verify source files against a delivery manifest from the repository root."""

import hashlib
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text())
for filename, expected in manifest["sha256"].items():
    actual = hashlib.sha256(Path(filename).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Source hash mismatch: {filename}")
print(f"Verified {len(manifest['sha256'])} source/configuration/fixture hashes.")
print(f"Verified source revision: {manifest['source_revision']}")
