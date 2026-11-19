"""Paced ASCII writes and bounded LEARN confirmation; no silent restart after acceptance."""
import re,time
from collections import deque

def parse_learning(line):
    if re.fullmatch(r'OK LEARN (?:30S|RUNNING)',line):return ('ack','LEARN','MCU已接收学习指令')
    if line=='OK CANCEL':return ('ack','CANCEL','MCU已取消学习')
    if line.startswith('ERR LEARN '):return ('error','LEARN',line)
    if line in ('ERR CAL session_active','ERR BUSY NVM pending','ERR BUSY RATE pending'):
        return ('error',None,line)
    return None

class CommandPacer:
    def __init__(self,interval=.08):self.interval=interval;self.last=-float('inf');self.items=deque()
    def add(self,cmd):
        if cmd=='CANCEL':self.items=deque(c for c in self.items if c!='LEARN')
        if cmd in ('CAL STATUS','CAL MONITOR 1','CAL INFO','CAL DATA','RATE?','LEARN','CANCEL') and cmd in self.items:return
        self.items.append(cmd)
    def take(self,now):
        if not self.items or now-self.last<self.interval:return None
        self.last=now;return self.items.popleft()

class LearningTransaction:
    def __init__(self,send,clock=time.monotonic):self.send=send;self.clock=clock;self.reset()
    def reset(self):
        self.cmd=None;self.phase=None;self.attempts=0;self.queued=0.;self.sent=0.;self.deadline=0.
        self.note='';self.notice_until=0.;self.accepted=False
    @property
    def pending(self):return (self.cmd,self.queued) if self.cmd else None
    def finish(self,note):
        self.cmd=None;self.phase=None;self.note=note;self.notice_until=self.clock()+8
    def request(self,cmd):
        if self.cmd and cmd!='CANCEL':return False
        self.cmd=cmd;self.phase='queued';self.attempts=0;self.queued=self.clock()
        self.deadline=self.clock()+8;self.sent=0;self.accepted=False
        self.note='学习指令已排队，等待串口发送。' if cmd=='LEARN' else '取消指令已排队，等待发送。'
        self.send(cmd);return True
    def event(self,stamp,event):
        kind,cmd,detail=event
        if not self.cmd or (cmd is not None and cmd!=self.cmd) or stamp<self.queued:return
        if kind=='sent':
            self.sent=stamp;self.attempts+=1;self.phase='ack';self.deadline=stamp+2
            self.note=f'学习指令已发送（第{self.attempts}次），等待 MCU 确认。' if self.cmd=='LEARN' else '取消已发送，等待 MCU 确认。'
        elif kind=='ack':
            if not self.attempts:return
            if self.cmd=='CANCEL':self.finish('MCU已确认取消学习。')
            else:
                self.accepted=True;self.phase='state';self.deadline=self.clock()+5
                self.note='MCU已接收学习指令，等待学习状态；请保持固定安装和正常工况。'
        elif kind=='error':
            reason=detail.replace('ERR LEARN busy','设备正忙（可能正在学习、保存或切换采样率）').replace('ERR LEARN sensor_not_ready','传感器尚未就绪').replace('ERR CAL session_active','六位置校准会话尚未结束，请先取消或保存校准').replace('ERR BUSY NVM pending','正在保存模型，请稍后再试').replace('ERR BUSY RATE pending','正在切换采样率，请稍后再试')
            self.finish('MCU拒绝操作：'+reason+'。本次不视为学习成功。')
    def observe(self,stamp,state):
        if self.cmd and self.attempts and stamp>=self.sent and ((self.cmd=='LEARN' and state==1) or (self.cmd=='CANCEL' and state!=1)):
            self.finish('MCU已进入正常状态学习，约1秒预热＋30秒有效数据。' if self.cmd=='LEARN' else 'MCU已退出学习状态。')
    def tick(self,connected):
        if not self.cmd:return
        now=self.clock()
        if not connected:self.finish('串口已断开，操作结果未确认。');return
        if now<=self.deadline:return
        if self.phase=='ack' and self.cmd=='LEARN' and not self.accepted and self.attempts<3:
            self.phase='queued';self.deadline=now+8;self.note='尚未收到 MCU 确认，正在有限重试。';self.send('LEARN')
        else:
            self.finish('MCU已接收指令，但未确认持续学习状态；请检查采集错误或复位日志。' if self.accepted else '操作未收到完整确认，已停止重试，请查看串口日志。')
