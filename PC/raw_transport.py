"""Dedicated CDC reader process, without NumPy/Qt or per-frame decoding."""
import multiprocessing as mp
import queue
import time
import sys
import json
from pathlib import Path
from collections import deque

def _reader(port,baud,out,commands,stop,ready):
    history=deque();history_bytes=0;received_bytes=0
    try:
        import serial
        with serial.Serial(port,baud,timeout=.005,write_timeout=.5) as ser:
            buffer_result=[]
            if sys.platform=='win32':
                for mib in (8,4,2,1):
                    try:
                        ser.set_buffer_size(rx_size=mib*1024*1024,tx_size=65536)
                        buffer_result.append(dict(rx_requested=mib*1024*1024,result='accepted'));break
                    except Exception as e:
                        buffer_result.append(dict(rx_requested=mib*1024*1024,result='failed',error=str(e)))
            ready.send(('ready',buffer_result));ready.close()
            while not stop.is_set():
                for _ in range(32):
                    try:cmd=commands.get_nowait()
                    except queue.Empty:break
                    if isinstance(cmd,dict) and cmd.get('action')=='snapshot':
                        path=Path(cmd['path'])
                        try:
                            content=b''.join(history)
                            path.write_bytes(content)
                            path.with_suffix('.json').write_text(json.dumps(dict(event='raw_snapshot',bytes=len(content),stream_end=received_bytes,stream_start=received_bytes-len(content),gap=cmd['gap']),ensure_ascii=False,indent=2),encoding='utf-8')
                        except Exception as exc:
                            try:path.with_suffix('.error.txt').write_text(str(exc),encoding='utf-8')
                            except Exception:pass
                        continue
                    if ser.write(cmd)!=len(cmd):raise IOError('USB command incomplete')
                b=ser.read(min(max(ser.in_waiting,1),65536))
                if b:
                    history.append(b);history_bytes+=len(b);received_bytes+=len(b)
                    while history and history_bytes>4*1024*1024:
                        history_bytes-=len(history.popleft())
                    # Never discard a block silently. Backpressure beyond this
                    # deadline is a visible failure, not a successful stream.
                    while not stop.is_set():
                        try:out.put(('data',b),timeout=.1);break
                        except queue.Full:
                            raise IOError('PC raw-byte queue full; receiving cannot keep up')
    except BaseException as e:
        try:ready.send(('error',repr(e)));ready.close()
        except Exception:pass
        try:out.put(('error',repr(e)),timeout=.2)
        except Exception:pass
    finally:
        try:out.put(('eof',None),timeout=.2)
        except Exception:pass

class ProcessSerial:
    def __init__(self,port,baud,timeout=.02,write_timeout=.5):
        ctx=mp.get_context('spawn')
        self.out=ctx.Queue(1024) # at most ~64 MiB of raw blocks
        self.commands=ctx.Queue(128);self.stop=ctx.Event()
        recv,send=ctx.Pipe(duplex=False)
        self.process=ctx.Process(target=_reader,args=(port,baud,self.out,self.commands,self.stop,send),daemon=True)
        self.buf=bytearray();self.timeout=timeout;self.closed=False
        self.process.start();send.close()
        if not recv.poll(15):
            self.close();raise IOError('USB reader process startup timeout')
        kind,value=recv.recv();recv.close()
        if kind!='ready':
            self.close();raise IOError(value)
        self.buffer_result=value
    @property
    def in_waiting(self):return len(self.buf)
    def read(self,n):
        if not self.buf:
            try:kind,value=self.out.get(timeout=self.timeout)
            except queue.Empty:
                if not self.process.is_alive():raise IOError('USB reader process exited')
                return b''
            if kind!='data':raise IOError(value or 'USB reader closed')
            self.buf.extend(value)
        result=bytes(self.buf[:n]);del self.buf[:n];return result
    def write(self,b):
        if not self.process.is_alive():raise IOError('USB reader process exited')
        self.commands.put(bytes(b),timeout=.5);return len(b)
    def snapshot(self,path,gap):
        self.commands.put(dict(action="snapshot",path=str(path),gap=gap),timeout=.5)
    def close(self):
        if self.closed:return
        self.closed=True;self.stop.set()
        self.process.join(1)
        if self.process.is_alive():self.process.terminate();self.process.join(1)
        self.out.cancel_join_thread();self.commands.cancel_join_thread()
        self.out.close();self.commands.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
