import os
import json
import time
import errno
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LocalFileClaimer:
    def __init__(self, base_dir: str = "logs/claims"):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_")
        return self.base / f"{safe}.lock"

    def acquire(self, key: str, ttl_seconds: int, run_id: str) -> bool:
        p = self._path(key)
        now = int(time.time())
        payload = {"run_id": run_id, "expires_at": now + ttl_seconds}
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(p, flags)
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(payload))
            logger.info(f"[CLAIM] acquired: {key} run_id={run_id}")
            return True
        except OSError as e:
            if e.errno != errno.EEXIST:
                logger.warning(f"[CLAIM] acquire error for {key}: {e}")
                return False
            # File exists; check TTL
            try:
                with open(p, "r") as f:
                    data = json.load(f)
                if int(data.get("expires_at", 0)) < now:
                    try:
                        os.remove(p)
                    except Exception:
                        pass
                    # Retry once
                    return self.acquire(key, ttl_seconds, run_id)
            except Exception:
                # Unreadable → consider it taken
                pass
            logger.info(f"[CLAIM] already held: {key}")
            return False

    def release(self, key: str) -> None:
        p = self._path(key)
        try:
            if p.exists():
                p.unlink()
                logger.info(f"[CLAIM] released: {key}")
        except Exception as e:
            logger.warning(f"[CLAIM] release error for {key}: {e}")


def create_local_claimer(enabled: bool = True, base_dir: Optional[str] = None) -> Optional[LocalFileClaimer]:
    if not enabled:
        return None
    return LocalFileClaimer(base_dir or "logs/claims")


