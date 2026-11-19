"""Continuity checks before the display queue; uint32 wrap is valid."""
class Continuity:
    def __init__(self):
        self.previous = None
        self.frames = self.events = 0
        self.counts = dict(seq=0, index=0, flags=0, rate=0)
    def feed(self, seq, fs, first, flags, count):
        old = self.previous
        reasons = []
        if old:
            if seq != old['next_seq']: reasons.append('seq')
            if first != old['next_index']: reasons.append('index')
            if fs != old['fs']: reasons.append('rate')
        if flags: reasons.append('flags')
        self.frames += 1
        self.previous = dict(seq=seq, first=first, count=count, fs=fs,
                             next_seq=(seq+1)&0xffffffff,
                             next_index=(first+count)&0xffffffff)
        if not reasons: return None
        self.events += 1
        for reason in reasons: self.counts[reason] += 1
        return dict(event='gap', reasons=reasons, previous=old,
                    current=dict(seq=seq,fs=fs,first=first,flags=flags,count=count),
                    seq_delta=None if not old else (seq-old['next_seq'])&0xffffffff,
                    index_delta=None if not old else (first-old['next_index'])&0xffffffff)
