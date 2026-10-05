"""Local ledger of follow-ups sent through the operator.

Stores, per ManyChat chat id, the last follow-up number (FUP 1, FUP 2, ...), the exact
text sent and when. It replaces manual tag bookkeeping: the cooldown is computed from
the timestamp, so nothing has to be "untagged" when the waiting period passes.

The file lives next to the browser profile (outside the repository) and holds only
chat ids, numbers, texts and timestamps. No conversation history is stored.
"""
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

LEDGER_PATH = Path.home() / ".tato-manychat-profile" / "followup-ledger.json"
DEFAULT_COOLDOWN_HOURS = 6.0
MAX_FOLLOWUPS = 2

_FUP_TAG = re.compile(r'^\s*(?:fup|fop|seguimiento)\s*[-_ ]?\s*(\d+)\s*$', re.IGNORECASE)
_LOCK = threading.Lock()


def normalize_text(text: Optional[str]) -> str:
    return re.sub(r'\s+', ' ', (text or '')).strip().lower()


def fup_number_from_tags(tags: Iterable[str]) -> int:
    """Highest follow-up number found in tags such as FUP1, FUP 2 or FOP-3. 0 if none."""
    best = 0
    for tag in tags or []:
        match = _FUP_TAG.match(str(tag))
        if match:
            best = max(best, int(match.group(1)))
    return best


class FollowupLedger:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or LEDGER_PATH

    def _load(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        tmp.replace(self.path)

    def get(self, lead_id: str) -> Optional[Dict[str, Any]]:
        with _LOCK:
            entry = self._load().get(str(lead_id))
        return entry if isinstance(entry, dict) else None

    def record_sent(self, lead_id: str, followup_number: int, text: str,
                    now: Optional[float] = None) -> None:
        if followup_number < 1:
            return
        with _LOCK:
            data = self._load()
            data[str(lead_id)] = {
                'fup': int(followup_number),
                'text': text,
                'sent_at': time.time() if now is None else now,
            }
            self._save(data)

    def cooling_down_ids(self, cooldown_hours: float, now: Optional[float] = None) -> Set[str]:
        """Chat ids whose last follow-up is more recent than the cooldown."""
        now = time.time() if now is None else now
        limit = max(0.0, cooldown_hours) * 3600
        with _LOCK:
            data = self._load()
        return {
            lead_id for lead_id, entry in data.items()
            if isinstance(entry, dict) and now - float(entry.get('sent_at', 0)) < limit
        }

    def prior_followup(self, lead_id: str, last_tato_text: Optional[str]) -> int:
        """Follow-up number already sent in the current cycle.

        Counts only when the last outbound message of the chat is the one we recorded;
        otherwise the lead answered (or Tato wrote something else) and a new cycle began.
        """
        entry = self.get(lead_id)
        if not entry or not last_tato_text:
            return 0
        if normalize_text(entry.get('text')) == normalize_text(last_tato_text):
            return int(entry.get('fup', 0))
        return 0


_ledger: Optional[FollowupLedger] = None


def get_ledger() -> FollowupLedger:
    global _ledger
    if _ledger is None:
        _ledger = FollowupLedger()
    return _ledger
