"""Spawn-only local analysis process: no GUI/GIL stall, no resident model."""
import multiprocessing
import os
import sys
import time
import threading

_NOTICE_PROCESS_LOCK=threading.Lock()

def _notice_child(operation, cache, payload, cancel, sender):
    """A receives public-only data; B alone receives local performance tuples."""
    calls=[]
    def audit(event,args):
        if event in ('socket.connect','socket.getaddrinfo','urllib.Request'):
            calls.append(event)
            raise RuntimeError('LOCAL_NOTICE_NETWORK_FORBIDDEN')
    sys.addaudithook(audit)
    started=time.perf_counter()
    try:
        from .notice_analysis import LocalNoticeAnalysis,public_only
        from .local_model import LocalEncoder
        service=LocalNoticeAnalysis(cache)
        if operation=='A': result=service.analyze_a([public_only(n) for n in payload],cancel=cancel)
        elif operation=='B': result=service.analyze_b(public_only(payload[0]),payload[1],cancel=cancel)
        else: raise ValueError('INVALID_LOCAL_STAGE')
        if calls: raise RuntimeError('LOCAL_NOTICE_NETWORK_FORBIDDEN')
        sender.send(('result',(result,dict(subprocess=True,external_calls=len(calls),
            elapsed_seconds=round(time.perf_counter()-started,3),active_sessions_after=LocalEncoder.active_sessions))))
    except Exception:
        sender.send(('error','LOCAL_NOTICE_ANALYSIS_UNAVAILABLE'))
    finally: sender.close()

def run_notice_analysis(operation, cache, payload, *, cancel=None):
    with _NOTICE_PROCESS_LOCK:
        if cancel and cancel.is_set(): raise RuntimeError('CANCELLED')
        return _run_notice_analysis(operation,cache,payload,cancel=cancel)

def _run_notice_analysis(operation, cache, payload, *, cancel=None):
    """UI worker thread supervises the existing spawn-only model architecture."""
    if operation=='A':
        from .notice_analysis import public_only
        payload=[public_only(n) for n in payload]
    context=multiprocessing.get_context('spawn')
    receiver,sender=context.Pipe(duplex=False)
    child_cancel=context.Event()
    process=context.Process(target=_notice_child,args=(operation,str(cache),payload,child_cancel,sender),
                            name='LocalNotice'+operation,daemon=True)
    started=False;deadline=time.monotonic()+180
    try:
        process.start();started=True;sender.close()
        while time.monotonic()<deadline:
            if cancel and cancel.is_set():
                child_cancel.set();raise RuntimeError('CANCELLED')
            if receiver.poll(.05):
                kind,value=receiver.recv()
                if kind=='result': return value
                raise RuntimeError('LOCAL_NOTICE_ANALYSIS_UNAVAILABLE')
            if not process.is_alive(): raise RuntimeError('LOCAL_NOTICE_PROCESS_FAILED')
        raise RuntimeError('LOCAL_NOTICE_ANALYSIS_TIMEOUT')
    finally:
        receiver.close();sender.close()
        if started:
            process.join(timeout=2)
            if process.is_alive(): process.terminate();process.join(timeout=2)
            process.close()


def _memory():
    if os.name != 'nt':
        return {}
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in
            ('peak', 'working', 'peak_paged', 'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private')]
    info = Counters()
    info.cb = ctypes.sizeof(info)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(info), info.cb):
        return {}
    return {name: round(getattr(info, name)/1024**2, 2) for name in ('working', 'peak', 'private')}


def _child(operation, source, database, force, cancel, sender):
    calls = []
    def audit(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo', 'urllib.Request'):
            calls.append(event)
            raise RuntimeError('ANALYSIS_NETWORK_FORBIDDEN')
    sys.addaudithook(audit)
    started, cpu = time.perf_counter(), time.process_time()
    try:
        from .enrichment import prepare_file, prepare_existing
        from .local_model import LocalEncoder
        progress = lambda current, total: sender.send(('progress', (current, total)))
        if operation == 'file':
            preview = prepare_file(source, database, progress=progress, cancel=cancel)
        else:
            preview = prepare_existing(database, progress=progress, cancel=cancel, force=force)
        preview.analysis_stats = {**preview.analysis_stats, 'subprocess': True, 'external_calls': len(calls),
            'wall_seconds': round(time.perf_counter()-started, 3), 'cpu_seconds': round(time.process_time()-cpu, 3),
            'memory_mib': _memory(), 'active_sessions_after': LocalEncoder.active_sessions}
        if calls:
            sender.send(('error', 'ANALYSIS_NETWORK_FORBIDDEN'))
        else:
            sender.send(('result', preview))
    except Exception as error:
        from .upload import UploadError
        sender.send(('error', str(error) if isinstance(error, UploadError) else 'FILE_READ_FAILED'))
    finally:
        sender.close()


def run_analysis(operation, source, database, *, force=False, progress=None, cancel=None):
    """Called from the UI's I/O thread. All heavy readers/model imports are child-only."""
    from .upload import UploadError
    context = multiprocessing.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    child_cancel = context.Event()
    process = context.Process(target=_child, args=(operation, source, database, force, child_cancel, sender),
                              name='LocalPerformanceAnalysis', daemon=True)
    started = False
    try:
        process.start()
        started = True
        sender.close()
        while True:
            if cancel and cancel.is_set():
                child_cancel.set()
            if receiver.poll(.05):
                kind, value = receiver.recv()
                if kind == 'progress':
                    if progress:
                        progress(*value)
                elif kind == 'result':
                    return value
                else:
                    raise UploadError(value)
            elif not process.is_alive():
                raise RuntimeError('ANALYSIS_PROCESS_FAILED')
    except (OSError, EOFError, RuntimeError):
        # A restricted machine may prevent starting a helper process. Preserve
        # the basic import path without running the model on the UI process.
        from .upload import preview_upload
        from .upload_store import load_enrichment_preview
        preview = preview_upload(source) if operation == 'file' else load_enrichment_preview(database)
        from .enrichment import _unknown
        for row in preview.rows:
            _unknown(row)
        preview.warnings.append('로컬 분석 모델을 사용할 수 없어 기본 분류로 저장했습니다.')
        return preview
    finally:
        receiver.close()
        sender.close()
        if started:
            process.join(timeout=2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            process.close()
