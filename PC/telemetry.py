"""Strict ASCII telemetry from MCU FFT V3 / Flash ECC V3."""
import re
FFT = re.compile(r'FFT valid=([01]) hz_x100=(\d+),(\d+),(\d+) amp_mg_x100=(\d+),(\d+),(\d+) windows=(\d+) skip=(\d+) age_ms=(\d+) step_max_ms=(\d+)')
NVM = re.compile(r'NVM init=(-?\d+) load=(-?\d+) save=(-?\d+) count=(\d+) seq=(\d+)')
SAVE = re.compile(r'NVM save=(-?\d+) count=(\d+) slot=(-?\d+) seq=(\d+) sensor_resume=(-?\d+)')
def parse_telemetry(line):
    line=line.strip()
    m=re.fullmatch(r'FFT valid=([01]) hz_x100=(\d+),(\d+),(\d+) amp_mg_x100=(\d+),(\d+),(\d+) windows=(\d+) skip=(\d+)',line)
    if m:
        v=list(map(int,m.groups()))
        if any(x>0xffffffff for x in v) or any(x>4000000 for x in v[1:4]) or any(x>100000000 for x in v[4:7]):return None
        return 'fft',dict(valid=bool(v[0]),hz=[x/100 for x in v[1:4]],amp=[x/100 for x in v[4:7]],windows=v[7],skip=v[8],age=None,step=None)
    m=re.fullmatch(r'FIFO samples/s=(\d+) level=(\d+) ovr=(\d+) errors=(\d+) UI_fps=(\d+) init=(-?\d+) LCD=(-?\d+) tx_drop=(\d+) stream_drop=(\d+) rx_ovf=(\d+)',line)
    if m:return 'h7fifo',dict(zip(('rate','level','overrun','errors','fps','init','lcd','txdrop','streamdrop','rxoverflow'),map(int,m.groups())))
    m=re.fullmatch(r'NVM save=(-?\d+) restart=(-?\d+) models=(\d+)',line)
    if m:return 'h7save',dict(zip(('save','restart','models'),map(int,m.groups())))
    m=re.search(r' NVM=(-?\d+)$',line) if line.startswith(('DETECT ','H743 FIFO ')) else None
    if m:return 'h7nvm',dict(code=int(m[1]))
    m=PERF.fullmatch(line)
    if m:
        v=list(map(int,m.groups()))
        if not 1<=v[0]<=60000 or not 0<=v[1]<=1000 or not 1<=v[8]<=4096:return None
        if v[6]>v[8] or v[7]>v[8] or any(x>0xffffffff for x in v):return None
        return 'perf',dict(zip(('period','busy','fft','lcd','lcd_max','fps','q','qmax','qcap'),v))
    m=FFT.fullmatch(line)
    if m:
        v=list(map(int,m.groups()))
        if any(x>0xffffffff for x in v) or any(x>4000000 for x in v[1:4]) or any(x>100000000 for x in v[4:7]): return None
        return 'fft',dict(valid=bool(v[0]),hz=[x/100 for x in v[1:4]],amp=[x/100 for x in v[4:7]],windows=v[7],skip=v[8],age=v[9],step=v[10])
    m=NVM.fullmatch(line)
    if m:
        v=list(map(int,m.groups()))
        if any(abs(x)>0xffffffff for x in v):return None
        return 'nvm',dict(init=v[0],load=v[1],save=v[2],count=v[3],seq=v[4])
    m=SAVE.fullmatch(line)
    if m:
        v=list(map(int,m.groups()))
        if any(abs(x)>0xffffffff for x in v) or v[2] not in (-1,0,1):return None
        return 'save',dict(save=v[0],count=v[1],slot=v[2],seq=v[3],resume=v[4])
    return None

RATE_CAPS=re.compile(r'RATE current=(\d+) supported=(\d+(?:,\d+)*)')
RATE_ACK=re.compile(r'OK RATE fs=(\d+)')
RATE_ERR=re.compile(r'ERR RATE(?: (.*))?')
def parse_rate(line):
    line=line.strip()
    m=RATE_CAPS.fullmatch(line)
    if m:
        current=int(m[1]); supported=tuple(map(int,m[2].split(',')))
        if len(supported)>32 or len(set(supported))!=len(supported) or current not in supported:return None
        if any(not 1<=x<=100000 for x in supported):return None
        return 'caps',dict(current=current,supported=supported)
    m=RATE_ACK.fullmatch(line)
    if m and 1<=int(m[1])<=100000:return 'ack',dict(current=int(m[1]))
    m=RATE_ERR.fullmatch(line)
    if m:return 'error',dict(reason=(m[1] or '设备拒绝切换')[:160])
    return None

PERF=re.compile(r'PERF period_ms=(\d+) busy_x10=(\d+) fft_ms=(\d+) lcd_ms=(\d+) lcd_max_ms=(\d+) fps_x10=(\d+) q=(\d+) qmax=(\d+) qcap=(\d+)')
