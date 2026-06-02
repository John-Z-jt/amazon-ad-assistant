import json
import os
from utils.path_tool import get_abs_path
from utils.config_handler import agent_conf

class FileHistoryStore:
    def __init__(self, storage_dir_path: str = get_abs_path(agent_conf["session_id_dir_path"])):

        self.storage_dir_path = storage_dir_path
        os.makedirs(storage_dir_path, exist_ok=True)

    def _get_path(self, session_id):
        return os.path.join(self.storage_dir_path, f"{session_id}.json")

    def get_history(self, session_id: str):
        path = self._get_path(session_id)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def add_message(self, session_id: str, role: str, content: str):
        history = self.get_history(session_id)
        history.append({"role": role, "content": content})
        with open(self._get_path(session_id), "w", encoding="utf-8") as f:
            json.dump(history, f,ensure_ascii= False)





