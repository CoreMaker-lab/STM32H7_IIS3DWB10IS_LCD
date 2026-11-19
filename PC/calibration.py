"""Six-face MCU calibration protocol and state; no PC-side correction of samples."""
import re
import time

FACES = ('X+', 'X-', 'Y+', 'Y-', 'Z+', 'Z-')

def parse_calibration(line):
    patterns = (
        ('info', r'CAL INFO fw=(\d+) rule=(\d+) rows=([01]) accel=([01])'),
        ('boot', r'MCU CAL V(\d+)\.(\d+) /.*'),
        ('actual', r'ACCEL mean_ug=(-?\d+),(-?\d+),(-?\d+) calibrated=([01])'),
        ('quality', r'CAL QUALITY rule=2 norm_ug=(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+) pair_ug=(\d+),(\d+),(\d+)'),
        ('row', r'CAL ROW face=(\d+) valid=([01]) raw_ug=(-?\d+),(-?\d+),(-?\d+) residual_ug=(-?\d+),(-?\d+),(-?\d+) checked=([01])'),
        ('check', r'CAL CHECK rc=(-?\d+) worst_face=(-?\d+) worst_axis=(-?\d+) max_ug=(\d+) span_ug=(-?\d+),(-?\d+),(-?\d+)'),
        ('monitor', r'OK CAL MONITOR ([01])'),
        ('live', r'CAL LIVE mean_ug=(-?\d+),(-?\d+),(-?\d+) std_ug=(\d+),(\d+),(\d+) stable=([01])'),
        ('status', r'CAL STATUS session=([01]) mask=(\d+) face=(-?\d+) samples=(\d+) target=(\d+) solved=([01]) pending=([01])'),
        ('params', r'CAL (ACTIVE|CANDIDATE) valid=([01]) offset_ug=(-?\d+),(-?\d+),(-?\d+) gain_ppm=(\d+),(\d+),(\d+)'),
        ('begin', r'OK CAL BEGIN version=1 capture_ms=5000'),
        ('face', r'OK CAL FACE (X\+|X-|Y\+|Y-|Z\+|Z-) samples=(\d+)'),
        ('done', r'CAL FACE_DONE rc=(-?\d+) mask=(\d+) mean_ug=(-?\d+),(-?\d+),(-?\d+)'),
        ('save_pending', r'OK CAL SAVE pending'),
        ('saved', r'CAL SAVE rc=(-?\d+) sensor_resume=(-?\d+) seq=(\d+) relearn=([01])'),
        ('cancel', r'OK CAL CANCEL'),
        ('error', r'ERR CAL (.+)'),
    )
    for kind, pattern in patterns:
        m = re.fullmatch(pattern, line)
        if not m:
            continue
        g = m.groups()
        if kind == 'info':
            n=tuple(map(int,g));return kind,dict(fw=n[0],rule=n[1],rows=n[2],accel=n[3])
        if kind == 'boot':return kind,(int(g[0]),int(g[1]))
        if kind == 'actual':
            n=tuple(map(int,g))
            if any(abs(x)>100000000 for x in n[:3]):return None
            return kind,dict(mean=n[:3],calibrated=bool(n[3]))
        if kind == 'quality':
            n=tuple(map(int,g))
            if any(abs(x)>100000000 for x in n):return None
            return kind,dict(norm=n[:6],pair=n[6:])
        if kind == 'row':
            n=tuple(map(int,g))
            if n[0]>5 or any(abs(x)>100000000 for x in n[2:8]):return None
            return kind,dict(face=n[0],valid=bool(n[1]),raw=n[2:5],residual=n[5:8],checked=bool(n[8]))
        if kind == 'check':
            n=tuple(map(int,g))
            if n[0] not in (0,-1,-2,-3,-4,-5) or not -1<=n[1]<6 or not -1<=n[2]<3 or n[3]>100000000:return None
            return kind,dict(rc=n[0],face=n[1],axis=n[2],maximum=n[3],span=n[4:7])
        if kind == 'live':
            values=tuple(map(int,g))
            if any(abs(x)>100000000 for x in values[:3]) or any(x>100000000 for x in values[3:6]):return None
            return kind,dict(mean=values[:3],std=values[3:6],stable=bool(values[6]))
        if kind == 'monitor':return kind,int(g[0])
        if kind == 'status':
            v = dict(zip(('session','mask','face','samples','target','solved','pending'), map(int,g)))
            if v['mask'] > 63 or not -1 <= v['face'] < 6 or v['samples'] > 160000 or v['target'] > 100000:
                return None
            return kind,v
        if kind == 'params':
            v = dict(kind=g[0],valid=int(g[1]),offset=tuple(map(int,g[2:5])),gain=tuple(map(int,g[5:8])))
            if any(abs(x)>5000000 for x in v['offset']) or any(not 850000<=x<=1150000 for x in v['gain']):
                return None
            if not v['valid'] and (v['offset']!=(0,0,0) or v['gain']!=(1000000,)*3):
                return None
            return kind,v
        if kind == 'face':
            if int(g[1]) not in (12500,25000,50000,100000):return None
            return kind,dict(face=FACES.index(g[0]),target=int(g[1]))
        if kind == 'done':
            if int(g[1])>63 or int(g[0]) not in (0,-1,-2):return None
            return kind,dict(rc=int(g[0]),mask=int(g[1]),mean=tuple(map(int,g[2:])))
        if kind == 'saved':
            return kind,dict(rc=int(g[0]),resume=int(g[1]),seq=int(g[2]),relearn=int(g[3]))
        return kind, g[0] if kind=='error' else None
    if line == 'ERR COMMAND':return 'unsupported',None
    return None

class Calibration:
    def __init__(self,send,clock=time.monotonic):
        self.send,self.clock=send,clock
        self.connected=False
        self.reset()
    def reset(self):
        self.known=False;self.session=False;self.mask=0;self.face=-1
        self.samples=0;self.target=0;self.solved=False;self.remote_pending=False
        self.pending=None;self.deadline=0;self.last_poll=0;self.candidate=None;self.active=None
        self.last_mean=None;self.last_face=None;self.success=False;self.verify=None
        self.note='连接设备后查询校准状态。';self.uncertain=False
        self.rows={};self.check=None;self.quality=None
        self.info=None;self.boot=None;self.info_wait=False;self.info_stamp=0;self.data_stamp=0;self.data_retries=0
        self.actual=None;self.actual_stamp=0
        self.live=None;self.live_stamp=0;self.monitoring=False;self.monitor_stamp=0
    @property
    def locked(self):
        return self.connected and (self.session or bool(self.pending) or self.remote_pending or self.uncertain)
    def connection(self,connected):
        if connected == self.connected:return
        self.connected=connected
        self.reset()
        if connected:
            self.note='正在核对 MCU 校准协议版本…';self.query();self.query_info()
        else:self.note='串口已断开；未确认的采集或保存不视为成功。重连后查询设备状态。'
    @property
    def link_ready(self):
        return bool(self.info and self.info['fw']>=104 and self.info['rule']==2 and self.info['rows'] and self.info['accel'])
    def version_text(self):
        if self.info:
            n=self.info['fw'];return f"MCU V{n//100}.{n%100} · 校准协议{'匹配' if self.link_ready else '不匹配，需V1.4'}"
        if self.boot:return f"MCU 启动标识 V{self.boot[0]}.{self.boot[1]}；尚未收到V1.4能力确认"
        return 'MCU版本未确认：需烧录V1.4，确认 main.c 和 calibration.inc 均已替换并重新编译。'
    def query_info(self):
        if self.connected and not self.remote_pending and self.pending not in ('save','verify'):
            self.send('CAL INFO');self.info_wait=True;self.info_stamp=self.clock()
    def monitor(self,enabled):
        enabled=bool(enabled and self.connected)
        if enabled!=self.monitoring:
            self.monitoring=enabled
            if self.connected and not self.remote_pending and self.pending not in ('save','verify'):
                self.send('CAL MONITOR '+str(int(enabled)));self.monitor_stamp=self.clock()
            if not enabled:self.live=None
    def actual_fresh(self):
        return self.connected and self.actual is not None and self.clock()-self.actual_stamp<2.0
    def live_fresh(self):
        return self.connected and self.live is not None and self.clock()-self.live_stamp<2.0
    def query(self):
        if self.connected:
            self.send('CAL STATUS');self.last_poll=self.clock()
    def query_data(self):
        if self.connected and not self.remote_pending and self.pending not in ('save','verify','face','begin'):
            self.send('CAL DATA');self.data_stamp=self.clock()
    def diagnostic_note(self):
        d=self.check
        if not d:return '设备拒绝求解，但六面诊断明细尚未返回；请查询设备状态并确认MCU版本。'
        if d['rc']==-4 and self.quality:
            f=max(range(6),key=lambda i:abs(self.quality['norm'][i]))
            return f"合量核验未通过：{FACES[f]} 面校正后合量偏离1g {self.quality['norm'][f]/1000:+.2f} mg（允许±50 mg），请检查该面倾斜及对应正反面基准。"
        if d['rc']==-5 and self.quality:
            a=max(range(3),key=lambda i:self.quality['pair'][i])
            return f"正反面对称性未通过：{'XYZ'[a]} 轴两面的校正中点偏差 {self.quality['pair'][a]/1000:.2f} mg（允许50 mg）。请检查这两面及各轴零偏是否稳定。"
        if d['rc']==-3 and d['face']>=0 and d['axis']>=0:
            return f"六面核验未通过：最大残差在 {FACES[d['face']]} 面的 {'XYZ'[d['axis']]} 轴，{d['maximum']/1000:.2f} mg（门限50 mg）。先检查该面，并核对该轴正反面；最大残差不能唯一确定问题来源。选中一面重采会保留其余数据。"
        if d['rc']==-2:
            return '正反面差值或参数不合格。X/Y/Z 正反面差值：'+', '.join(f'{v/1000:.2f}' for v in d['span'])+' mg；各轴应约为+2000 mg，请检查是否选错方向、重复同一面或正反面颠倒。'
        return '六面数据尚未齐全，请补采缺失面。' if d['rc']==-1 else '零偏/比例及综合一致性检查通过。'
    def request(self,kind,face=None):
        if not self.connected or not self.known or self.remote_pending:return False
        if self.pending and not (kind=='cancel' and self.pending not in ('save','verify','cancel')):return False
        if self.uncertain and kind!='cancel':return False
        if kind in ('begin','face','solve','save') and not self.link_ready:
            self.note=self.version_text();return False
        if kind=='begin':
            if self.session:return False
            cmd='CAL BEGIN'
        elif kind=='cancel':cmd='CAL CANCEL'
        elif kind=='face':
            if not self.session or self.face>=0 or face not in range(6):return False
            cmd='CAL FACE '+FACES[face];self.last_face=face;self.last_mean=None
            self.candidate=None;self.solved=False;self.check=None;self.quality=None
            for row in self.rows.values():row['checked']=False
        elif kind=='solve':
            if not self.session or self.mask!=63 or self.face>=0:return False
            cmd='CAL SOLVE';self.candidate=None;self.check=None;self.quality=None
        elif kind=='save':
            if not self.session or not self.solved or not self.candidate:return False
            cmd='CAL SAVE';self.success=False;self.verify=None
        else:return False
        self.pending=kind;self.deadline=self.clock()+(11 if kind=='face' else 8)
        self.note={'begin':'等待 MCU 开始校准确认…','face':'保持静止，正在采集这一面…',
                   'solve':'等待 MCU 计算和检查六面结果…','save':'正在写入设备，等待最终结果；请勿断电。',
                   'cancel':'等待 MCU 取消确认…'}[kind]
        self.send(cmd);return True
    def event(self,event):
        if not self.connected:return
        kind,v=event
        if kind=='info':
            self.info=v;self.info_wait=False
            if not self.link_ready:self.note=self.version_text()
            return
        if kind=='boot':
            self.boot=v;return
        if kind=='actual':
            self.actual=v;self.actual_stamp=self.clock();return
        if kind=='quality':
            if self.pending not in ('face','begin'):self.quality=v
            return
        if kind=='row':
            if self.pending not in ('face','begin'):self.rows[v['face']]=v
            return
        if kind=='check':
            if self.pending not in ('face','begin'):
                self.check=v
                if v['rc']<0:self.note=self.diagnostic_note()
            return
        if kind=='live':
            self.live=v;self.live_stamp=self.clock();return
        if kind=='monitor':return
        if kind=='status':
            was_known=self.known;old_mask=self.mask
            self.known=True;self.session=bool(v['session']);self.mask=v['mask'];self.face=v['face']
            self.samples=v['samples'];self.target=v['target'];self.solved=bool(v['solved']);self.remote_pending=bool(v['pending'])
            if (not was_known or old_mask!=self.mask) and self.mask:self.query_data()
            if self.uncertain and not self.remote_pending:
                self.uncertain=False
                self.note='已重新查询设备。上次操作结果未确认，请检查参数；不要将此提示当作保存成功。'
            elif not was_known and not self.pending and not self.success:
                self.note='校准会话进行中，可继续采集或取消。' if self.session else '设备支持六位置校准。先停机，将板子静止放稳。'
        elif kind=='params':
            if v['kind']=='ACTIVE':
                self.active=v
                if self.pending=='verify' and self.verify:
                    if v['valid']==1 and v['offset']==self.verify['offset'] and v['gain']==self.verify['gain']:
                        self.success=True;self.pending=None
                        self.note='保存成功，已读回当前参数。请安装到正常工况，分别重新学习 2500 / 5000 / 10000 / 20000 Hz；掉电恢复需重启后另行验证。'
                    else:
                        self.pending=None;self.note='保存回复与读回参数不一致，请检查设备。';self.query()
            elif self.pending=='solve' and v['valid']==1:
                self.candidate=v;self.solved=True;self.pending=None
                self.note='零偏/比例与综合一致性检查通过，可以保存。旁轴残差超过50 mg仅提示检查姿态；写入后须重新学习。'
        elif kind=='begin' and self.pending=='begin':
            self.session=True;self.mask=0;self.solved=False;self.candidate=None;self.success=False;self.last_mean=None;self.rows={};self.check=None;self.quality=None
            self.pending=None;self.note='按六个方向逐面放稳，再点击“采集所选面”。';self.query()
        elif kind=='face' and self.pending=='face':
            if v['face']!=self.last_face:
                self.pending=None;self.uncertain=True;self.note='采集方向回复不匹配，请查询设备状态。';self.query()
            else:self.face=v['face'];self.target=v['target'];self.samples=0
        elif kind=='done':
            self.mask=v['mask'];self.face=-1;self.last_mean=v['mean']
            if self.last_face is not None and v['rc']==0:
                self.rows[self.last_face]=dict(face=self.last_face,valid=True,raw=v['mean'],residual=(0,0,0),checked=False)
            if self.pending=='face':self.pending=None
            self.data_retries=0;self.query_data()
            self.note='本面静止检查通过，可以换下一面；方向和零偏将在六面求解时核验。' if v['rc']==0 else '本面未通过：'+('采集期间有振动，请放稳重试；方向会在六面求解时检查。' if v['rc']==-1 else '采集数据中断或超时，请重试。')
        elif kind=='save_pending' and self.pending=='save':self.remote_pending=True
        elif kind=='saved':
            if self.pending!='save':
                self.note='收到延迟的保存回复，请查询当前参数并检查设备。';self.query();return
            self.remote_pending=False
            if v['rc']==0 and v['resume']==0 and v['relearn']==1 and self.candidate:
                self.session=False;self.verify=self.candidate.copy();self.pending='verify'
                self.deadline=self.clock()+5;self.note='MCU 已确认保存，正在读回参数…';self.query()
            else:
                self.pending=None;self.uncertain=True
                self.note=f"保存未完整确认：写入返回 {v['rc']}，传感器恢复 {v['resume']}。请查询参数；可能已提交，需要重新学习。"
                self.query()
        elif kind=='cancel' and self.pending=='cancel':
            self.pending=None;self.session=False;self.face=-1;self.solved=False;self.candidate=None
            self.note='已取消未保存的校准；原有参数保持。';self.query()
        elif kind in ('error','unsupported'):
            if self.info_wait and ((kind=='error' and v=='command') or kind=='unsupported'):
                self.info_wait=False;self.note=self.version_text();return
            self.pending=None
            self.note=((self.diagnostic_note()+' [设备返回 '+str(v)+']') if str(v).startswith('SOLVE ') else 'MCU 拒绝操作：'+str(v)) if kind=='error' else '固件不支持校准命令，请使用 MCU_Calibration_V1。'
            if kind=='unsupported':self.known=False
            else:self.query()
    def tick(self):
        if not self.connected:return
        now=self.clock()
        missing=any(self.mask&(1<<i) and (i not in self.rows or not self.rows[i]['valid']) for i in range(6))
        if self.link_ready and self.session and missing and not self.pending and not self.remote_pending and now-self.data_stamp>2:
            if self.data_retries<3:
                self.query_data();self.data_retries+=1
            else:self.note='MCU报告已采集，但六面明细未完整返回。请检查当前固件版本及串口日志；缺失值不会被当成0。'
        if self.info_wait and now-self.info_stamp>3:
            self.info_wait=False
            if not self.link_ready:self.note=self.version_text()
        if self.monitoring and now-self.monitor_stamp>=2 and not self.remote_pending and self.pending not in ('save','verify'):
            self.send('CAL MONITOR 1');self.monitor_stamp=now
        if not self.known and now-self.last_poll>5:
            self.note='未收到校准能力回复。请检查是否使用 MCU_Calibration_V1；原有采集功能仍可使用。'
        if self.pending and now>self.deadline:
            name=self.pending;self.pending=None;self.uncertain=True;self.success=False
            self.note=f'{name} 未收到完整确认，结果未知；正在查询设备，请勿重复写入。';self.query()
        if now-self.last_poll>=1 and (self.session or self.remote_pending or self.uncertain):self.query()
