from pathlib import Path

def check_output_path(store,destination):
    """Keep generated exports/backups out of the application's live storage."""
    p=Path(destination).resolve()
    db=store.db_path.resolve(); originals=(store.data_dir/'originals').resolve()
    protected={db,db.with_name(db.name+'-wal'),db.with_name(db.name+'-shm'),db.with_name(db.name+'-journal'),(store.data_dir/'instance.lock').resolve()}
    if p in protected or p==originals or p.is_relative_to(originals):
        raise ValueError('데이터베이스·원본·잠금 파일을 출력 대상으로 덮어쓸 수 없습니다. 다른 경로를 선택하세요.')
    return p
