import uuid
import os

def generate_id() -> str:
    return str(uuid.uuid4())[:8]

def default_shell() -> str:
    if os.name == "posix":
        return os.environ.get("SHELL")
    elif os.name == "nt":
        return os.environ.get("COMSPEC")
    return
