"""Settings adapter for a single-writer Windows host; unrelated keys preserved."""
import json, os, tempfile
from pathlib import Path
from .escort_settings_trial100 import EscortSettings as Previous

class EscortSettings(Previous):
    def merge(self, existing):
        if not isinstance(existing, dict): raise ValueError('settings object expected')
        return {**existing, **json.loads(self.to_json())}

    @classmethod
    def load(cls, path):
        p=Path(path)
        try: data=p.read_text(encoding='utf-8-sig')
        except FileNotFoundError: return cls()
        return cls.from_json(data)

    def save(self, path):
        p=Path(path)
        try: existing=json.loads(p.read_text(encoding='utf-8-sig'))
        except FileNotFoundError: existing={}
        merged=self.merge(existing)
        payload=json.dumps(merged,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        # Same directory for atomic replacement; never overwrite corrupt JSON.
        fd,tmp=tempfile.mkstemp(prefix='.'+p.name+'.',suffix='.tmp',dir=p.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                f.write(payload);f.flush();os.fsync(f.fileno())
            os.replace(tmp,p)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        return merged
