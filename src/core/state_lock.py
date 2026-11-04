"""OS-held single writer lock; released on process death, without stale-file deletion."""
import os
from contextlib import contextmanager


@contextmanager
def state_writer(data_dir):
    data_dir.mkdir(parents=True,exist_ok=True)
    handle = (data_dir/'.central-writer.lock').open('a+b')
    acquired = False
    try:
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            if not handle.read(1):
                handle.write(b'0');handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        acquired = True
        yield
    except OSError as error:
        if not acquired:
            raise ValueError('CENTRAL_WRITER_BUSY') from error
        raise
    finally:
        if acquired:
            if os.name == 'nt':
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
        handle.close()
