import hashlib
import os
from pathlib import Path
from .hwpx import extract_text

def import_confirmed(store,source,data,questions):
    source=Path(source)
    extract_text(source)  # Validate archive before persisting anything.
    raw=source.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
    existing=store.find_hash(digest)
    if existing: raise ValueError('동일한 원본이 이미 등록되어 있습니다: '+existing['title'])
    relative=Path('originals')/(digest+'.hwpx'); target=store.data_dir/relative
    existed=target.exists()
    if existed and hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
        raise ValueError('원본 보관 파일의 무결성을 확인할 수 없습니다.')
    data=dict(data,original_name=source.name,file_hash=digest,original_path=relative.as_posix())
    if not existed:
        temp=target.with_suffix('.tmp')
        try:
            with temp.open('xb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
            temp.replace(target)
        finally:
            if temp.exists(): temp.unlink()
    try:
        return store.save_set(data,questions)
    except Exception:
        if not existed: target.unlink(missing_ok=True)
        raise
