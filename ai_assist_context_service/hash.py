import hashlib
import json


def hash_content(content):
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def stable_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
