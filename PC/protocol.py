"""V1 little-endian raw XYZ protocol; CRC32 matches zlib."""
import struct
import zlib
import numpy as np
MAGIC = b'\xa5\x5a\xc3\x3c'
HEADER = struct.Struct('<4sBBHIIIHH')

def encode(raw, seq=0, fs=2500, first=0, flags=0, compact=False):
    raw = np.asarray(raw, dtype='<i4').reshape(-1, 3)
    if compact:
        if np.any(raw < -8388608) or np.any(raw > 8388607):raise ValueError('signed24 range')
        payload=np.stack((raw&255,(raw>>8)&255,(raw>>16)&255),axis=-1).astype('u1').tobytes()
    else:payload = raw.tobytes()
    data = HEADER.pack(MAGIC, 1, 2 if compact else 1, len(payload), seq, fs, first, len(raw), flags) + payload
    return data + struct.pack('<I', zlib.crc32(data))

class Parser:
    def __init__(self):
        self.buf = bytearray()
        self.errors = 0
        self.text = bytearray()
    def feed(self, data):
        self.buf.extend(data)
        packets, logs = [], []
        def log_bytes(b):
            self.text.extend(b)
            while b'\n' in self.text:
                line, _, rest = self.text.partition(b'\n')
                self.text = bytearray(rest)
                logs.append(line.decode('utf-8', errors='replace').strip())
            if len(self.text) > 4096:
                self.text.clear()
        while True:
            pos = self.buf.find(MAGIC)
            if pos < 0:
                # Retain ONLY a possible partial binary magic prefix. A complete
                # ASCII ACK must not wait for some future packet to release its newline.
                keep=0
                for suffix in (3,2,1):
                    if len(self.buf)>=suffix and self.buf[-suffix:]==MAGIC[:suffix]:
                        keep=suffix;break
                n = len(self.buf)-keep
                log_bytes(self.buf[:n]); del self.buf[:n]
                break
            if pos:
                log_bytes(self.buf[:pos]); del self.buf[:pos]
            if len(self.buf) < HEADER.size:
                break
            _, ver, kind, length, seq, fs, first, count, flags = HEADER.unpack_from(self.buf)
            if ver != 1 or kind not in (1,2) or not 1 <= count <= 256 or length != count*(9 if kind==2 else 12) or not 1 <= fs <= 1000000:
                self.errors += 1; del self.buf[0]; continue
            size = HEADER.size + length + 4
            if len(self.buf) < size:
                break
            expected, = struct.unpack_from('<I', self.buf, size-4)
            if zlib.crc32(self.buf[:size-4]) != expected:
                self.errors += 1; self.text.clear(); del self.buf[:size]; continue
            payload=bytes(self.buf[HEADER.size:size-4])
            if kind==2:
                b=np.frombuffer(payload,dtype='u1').reshape(count,3,3).astype(np.int32)
                bits=b[:,:,0] | (b[:,:,1]<<8) | (b[:,:,2]<<16)
                raw=(bits ^ 0x800000)-0x800000
            else:raw=np.frombuffer(payload,dtype='<i4').reshape(count,3)
            packets.append((seq, fs, first, flags, raw))
            del self.buf[:size]
        return packets, logs

def spectrum(mg, fs):
    """One-sided Hann amplitude, mg; DC removed."""
    n = len(mg)
    if n < 8:
        return np.empty(0), np.empty((0, 3))
    w = np.hanning(n)
    y = mg - mg.mean(axis=0)
    amplitude = np.abs(np.fft.rfft(y*w[:, None], axis=0))*2/w.sum()
    amplitude[0] *= .5
    if n % 2 == 0:
        amplitude[-1] *= .5
    return np.fft.rfftfreq(n, 1/fs), amplitude
