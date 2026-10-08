"""OS-owned lock: automatically released even when the app crashes."""
import os
from pathlib import Path

class InstanceLock:
    def __init__(self,path):
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        self.file=path.open('a+b')
        if path.stat().st_size==0: self.file.write(b'0'); self.file.flush()
        self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as e:
            self.file.close()
            raise ValueError('이 데이터 폴더를 사용하는 프로그램이 이미 실행 중입니다.') from e
    def close(self):
        if self.file.closed: return
        if os.name=='nt':
            import msvcrt
            self.file.seek(0); msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(self.file.fileno(),fcntl.LOCK_UN)
        self.file.close()
