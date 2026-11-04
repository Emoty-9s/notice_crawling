"""CPU/RAM measurement on synthetic tests-only workloads, with HTTP blocked."""
import ctypes
import json
import platform
import socket
import sys
import time
from ctypes import wintypes
from pathlib import Path
from urllib.request import OpenerDirector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_client.upload import UploadRow
from src.local_client.local_model import LocalEncoder
from src.local_client.enrichment import enrich_rows


class Counters(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
        'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage',
        'PeakPagefileUsage', 'PrivateUsage')]


def memory():
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise OSError('MEMORY_COUNTER_FAILED')
    return {name: round(getattr(counters, name)/1024**2, 2) for name in ('WorkingSetSize', 'PeakWorkingSetSize', 'PrivateUsage')}


def main():
    calls = []
    def deny(*args, **kwargs):
        calls.append(True)
        raise RuntimeError('HTTP_FORBIDDEN')
    OpenerDirector.open = socket.create_connection = deny
    cases = json.loads((Path(__file__).parent/'fixtures/performance_enrichment/heldout.json').read_text(encoding='utf-8'))
    values = []
    for index in range(300):
        case = cases[index % len(cases)]
        text = '\n'.join(v for v in (case.get('title'), case.get('description')) if v)
        values.append(UploadRow('benchmark', index+1, None, case.get('title'), None, None, None, None,
                                '', '', text, (), None, {'columns': {'title': case.get('title'), 'description':text}},
                                text, text, str(index)))
    before = memory()
    started, cpu = time.perf_counter(), time.process_time()
    updates = []
    warning = enrich_rows(values, progress=lambda current, total: updates.append(current))
    result = {'rows':len(values), 'wall_seconds':round(time.perf_counter()-started, 3),
              'cpu_seconds':round(time.process_time()-cpu, 3), 'before_mib':before, 'after_mib':memory(),
              'active_sessions_after':LocalEncoder.active_sessions, 'external_calls':len(calls),
              'progress_final':updates[-1], 'warning':warning, 'machine':platform.machine(),
              'classified_technical':sum(v.technical_field != '미분류' for v in values)}
    idle = time.process_time()
    time.sleep(.5)
    result['idle_cpu_seconds_over_half_second'] = round(time.process_time()-idle, 6)
    output = Path('.run/local-model-benchmark.json')
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
