import os
import sys


def _ensure_project_root_on_path() -> None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    # project_root -> /mnt/tg_bot_picture_v1
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


_ensure_project_root_on_path()


