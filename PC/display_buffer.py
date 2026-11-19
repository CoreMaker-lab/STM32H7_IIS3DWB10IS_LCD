"""Fixed-size sample ring; retain samples without one Python object per row."""
import numpy as np
class SampleRing:
    def __init__(self,capacity=131072):
        self.capacity=capacity;self.buffer=np.empty((capacity,3),dtype=np.float64)
        self.end=self.size=0
    def __len__(self):return self.size
    def clear(self):self.end=self.size=0
    def extend(self,rows):
        x=np.asarray(rows,dtype=np.float64).reshape(-1,3)
        if len(x)>=self.capacity:x=x[-self.capacity:]
        n=len(x);part=min(n,self.capacity-self.end)
        self.buffer[self.end:self.end+part]=x[:part]
        if part<n:self.buffer[:n-part]=x[part:]
        self.end=(self.end+n)%self.capacity;self.size=min(self.capacity,self.size+n)
    def tail(self,count):
        n=min(max(0,int(count)),self.size)
        start=(self.end-n)%self.capacity
        if start+n<=self.capacity:return self.buffer[start:start+n].copy()
        return np.concatenate((self.buffer[start:],self.buffer[:self.end]))
