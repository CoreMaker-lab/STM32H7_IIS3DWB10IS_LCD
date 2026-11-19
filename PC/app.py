"""Real-serial desktop vibration monitor. Run python app.py."""
import sys, time, queue, threading, csv, json, datetime
from continuity import Continuity
from raw_transport import ProcessSerial
from display_buffer import SampleRing
from collections import deque
from pathlib import Path
import numpy as np
import serial
from serial.tools import list_ports
from PySide6 import QtCore, QtWidgets, QtGui
import pyqtgraph as pg
from protocol import Parser, spectrum
from detection import parse_detection, STATES
from telemetry import parse_telemetry, parse_rate
from calibration import Calibration, parse_calibration
from calibration_ui import CalibrationDialog
from learning_control import CommandPacer, LearningTransaction, parse_learning

class Receiver(threading.Thread):
    def __init__(self, port, baud):
        super().__init__(daemon=True)
        self.port, self.baud = port, baud
        self.commands, self.packets, self.logs = queue.Queue(), queue.Queue(2048), queue.Queue(256)
        self.detections = queue.Queue(64)
        self.telemetry = queue.Queue(64)
        self.rate_events = queue.Queue(32)
        self.cal_events = queue.Queue(64)
        self.learning_events=queue.Queue(64)
        self.last_sample = 0.0
        self.is_h7 = False
        self.connected = False
        self.stop_event = threading.Event()
        self.parser = Parser()
        self.drops = self.received = self.recorded = 0
        self.recording = False
        self.file = None
        self.continuity = Continuity()
        self.diag = None
        self.diag_tick = 0.0
        self.snapshots = 0
    def diagnostic(self, event):
        if self.diag:
            event = dict(event, elapsed_s=round(time.monotonic()-self.diag_started,6))
            self.diag.write(json.dumps(event,ensure_ascii=False)+"\n")
            self.diag.flush()
    def learning_event(self,event,stamp=None):
        try:self.learning_events.put_nowait((time.monotonic() if stamp is None else stamp,event))
        except queue.Full:
            self.learning_events.get_nowait();self.learning_events.put_nowait((time.monotonic(),event))
    def log(self, text):
        if text.startswith(("FIFO ","FFT ","DETECT ","OK ","ERR ","RATE ","USBTRACE ")):
            self.diagnostic(dict(event="mcu_text",text=text))
        if text.startswith(('H743 FIFO ','FIFO samples/s=')) or (text.startswith('DETECT ') and ' NVM=' in text):self.is_h7=True
        learning=parse_learning(text)
        if learning:self.learning_event(learning)
        cal=parse_calibration(text)
        if cal:
            try:self.cal_events.put_nowait(cal)
            except queue.Full:
                self.cal_events.get_nowait();self.cal_events.put_nowait(cal)
        rate=parse_rate(text)
        if rate:
            try:self.rate_events.put_nowait((time.monotonic(),rate))
            except queue.Full:
                self.rate_events.get_nowait();self.rate_events.put_nowait((time.monotonic(),rate))
        telemetry = parse_telemetry(text)
        if telemetry:
            try: self.telemetry.put_nowait((time.monotonic(),telemetry))
            except queue.Full:
                self.telemetry.get_nowait();self.telemetry.put_nowait((time.monotonic(),telemetry))
        detection = parse_detection(text)
        if detection:
            try: self.detections.put_nowait((time.monotonic(), detection))
            except queue.Full:
                self.detections.get_nowait()
                self.detections.put_nowait((time.monotonic(), detection))
        # MCU text is ASCII; reject damaged/binary leftovers rather than displaying mojibake.
        if not text or any(ord(c) < 32 or ord(c) == 65533 for c in text): return
        try: self.logs.put_nowait(text)
        except queue.Full: pass
    def run(self):
        connection = None
        try:
            connection = ProcessSerial(self.port, self.baud, timeout=.02, write_timeout=.5)
            self.diag_started=time.monotonic()
            folder=Path(__file__).resolve().parent/"diagnostics"
            folder.mkdir(exist_ok=True)
            self.diag_path=folder/(datetime.datetime.now().strftime("continuity_%Y%m%d_%H%M%S_%f")+".jsonl")
            self.diag=self.diag_path.open("w",encoding="utf-8")
            self.diagnostic(dict(event="open",port=self.port,baud=self.baud))
            # Windows default driver buffers can be too small when GUI work
            # delays the Python receiver. Keep acquisition independent of draw cadence.
            for result in connection.buffer_result:
                self.diagnostic(dict(event="driver_buffer",**result))
            self.log("USB接收：独立进程，原始字节队列最多约64 MiB")
            self.diagnostic(dict(event="transport",mode="dedicated_process"))
            self.connected = True
            self.log("连续性日志："+str(self.diag_path))
            self.commands.put(('STOP',None));self.commands.put(('STATUS',None));self.commands.put(('RATE?',None))
            self.log(f'已打开串口：{self.port}，配置波特率 {self.baud} bps')
            outbox=CommandPacer()
            while not self.stop_event.is_set():
                while not self.commands.empty():
                    cmd, value = self.commands.get_nowait()
                    if cmd == 'record':
                        if self.file: self.file.close(); self.file = None
                        self.recording = False
                        if value:
                            self.file = open(value, 'w', newline='', encoding='utf-8-sig')
                            self.writer = csv.writer(self.file)
                            self.writer.writerow(['seq','sample_index','fs_Hz','flags','raw_x','raw_y','raw_z','x_mg','y_mg','z_mg'])
                            self.recording = True
                        self.log('CSV 保存中' if value else 'CSV 已关闭')
                    else:
                        outbox.add(cmd)
                cmd=outbox.take(time.monotonic())
                if cmd is not None:
                    self.diagnostic(dict(event='command',command=cmd))
                    payload=(cmd+'\n').encode('ascii')
                    if connection.write(payload)!=len(payload):raise IOError('串口指令未完整写出')
                    if cmd in ('LEARN','CANCEL'):
                        self.learning_event(('sent',cmd,''));self.log('PC TX '+cmd)
                data = connection.read(min(max(connection.in_waiting, 1), 16384))
                packets, logs = self.parser.feed(data)
                for line in logs:
                    if line: self.log(line)
                for packet in packets:
                    seq, fs, first, flags, raw = packet
                    gap=self.continuity.feed(seq,fs,first,flags,len(raw))
                    if gap:
                        self.diagnostic(gap)
                        if 'seq' in gap['reasons'] and gap['current']['flags']==0 and self.snapshots<3:
                            self.snapshots+=1
                            path=self.diag_path.with_name(self.diag_path.stem+f"_gap{self.snapshots}.bin")
                            try:
                                connection.snapshot(path,gap)
                                missing=(gap['previous']['seq']+1)&0xffffffff
                                for query_seq in ((missing-1)&0xffffffff,missing,(missing+1)&0xffffffff):
                                    connection.write(f"USBTRACE {query_seq}\n".encode('ascii'))
                                self.diagnostic(dict(event="usbtrace_requested",seq=missing))
                                self.diagnostic(dict(event="snapshot_requested",path=str(path)))
                                self.log("原始断点快照："+str(path))
                            except Exception as exc:
                                self.diagnostic(dict(event="snapshot_request_failed",error=str(exc)))
                        self.log("CONTINUITY "+json.dumps(gap,ensure_ascii=False))
                    self.received += len(raw)
                    self.last_sample = time.monotonic()
                    if self.file:
                        mg = raw*.095
                        self.writer.writerows([seq,(first+i)&0xffffffff,fs,flags,*r,*m] for i,(r,m) in enumerate(zip(raw,mg)))
                        self.recorded += len(raw)
                    try: self.packets.put_nowait(packet)
                    except queue.Full: self.drops += 1
                if time.monotonic()-self.diag_tick>=1:
                    self.diag_tick=time.monotonic()
                    self.diagnostic(dict(event="summary",frames=self.continuity.frames,samples=self.received,events=self.continuity.events,counts=self.continuity.counts.copy(),crc_errors=self.parser.errors,display_drops=self.drops))
        except Exception as exc:
            self.log('错误: '+str(exc))
        finally:
            if self.diag:
                self.diagnostic(dict(event="close",events=self.continuity.events,counts=self.continuity.counts.copy()))
                self.diag.close();self.diag=None
            if self.file: self.file.close()
            self.recording = False
            self.connected = False
            if connection:
                try: connection.write(b'STOP\n')
                except Exception: pass
                connection.close()
            self.log('连接已关闭')

class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        families=set(QtGui.QFontDatabase.families())
        for family in ('Microsoft YaHei','Microsoft YaHei UI','Noto Sans CJK SC','SimHei'):
            if family in families:
                QtWidgets.QApplication.instance().setFont(QtGui.QFont(family,9))
                break
        self.setWindowTitle('三轴振动监测 · H743 USB FS · 40/80K试验版')
        self.resize(1280, 900)
        self.worker = None
        self.data = SampleRing(131072)
        self.fs = 2500
        self.previous = None
        self.gaps = 0
        self.last_fft = 0
        self.record_path = None
        self.perf_value=None;self.perf_stamp=0.0
        self.mcu_fft_value = None; self.mcu_fft_stamp = 0.0
        self.nvm_value = None; self.nvm_stamp = 0.0
        self.last_detection = None
        self.detect_time = 0.0
        self.score_origin = time.monotonic()
        self.scores = deque(maxlen=600)
        self.pending_command = None
        self.learning_tx=LearningTransaction(self.command)
        self.rate_supported=();self.rate_pending=None;self.rate_query_stamp=None
        self.calibration=Calibration(self.command)
        self.cal_dialog=CalibrationDialog(self.calibration,self)
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        layout = QtWidgets.QVBoxLayout(root);layout.setContentsMargins(8,6,8,6);layout.setSpacing(4)
        bar = QtWidgets.QHBoxLayout(); layout.addLayout(bar)
        self.ports = QtWidgets.QComboBox(); bar.addWidget(self.ports)
        refresh = QtWidgets.QPushButton('刷新串口'); refresh.clicked.connect(self.refresh); bar.addWidget(refresh)
        self.baud = QtWidgets.QComboBox(); self.baud.addItems(['115200','921600','2000000','3000000','4000000','6000000']);self.baud.setCurrentText('115200');self.baud.setToolTip('原生USB CDC不受此波特率限制；当前默认115200。');bar.addWidget(self.baud)
        self.connect_button = QtWidgets.QPushButton('连接'); self.connect_button.clicked.connect(self.connect_port); bar.addWidget(self.connect_button)
        self.start = QtWidgets.QPushButton('开始采集'); self.start.clicked.connect(lambda: self.command('START')); bar.addWidget(self.start)
        self.stop = QtWidgets.QPushButton('停止采集'); self.stop.clicked.connect(lambda: self.command('STOP')); bar.addWidget(self.stop)
        self.record = QtWidgets.QPushButton('保存 CSV'); self.record.clicked.connect(self.toggle_record); bar.addWidget(self.record)
        rate_bar=QtWidgets.QHBoxLayout();layout.addLayout(rate_bar)
        rate_bar.addWidget(QtWidgets.QLabel('传感器采样率'))
        self.rate_combo=QtWidgets.QComboBox();self.rate_combo.addItem('等待 MCU 支持列表');self.rate_combo.setEnabled(False);rate_bar.addWidget(self.rate_combo)
        self.rate_query=QtWidgets.QPushButton('查询采样率');self.rate_query.clicked.connect(self.query_rate);rate_bar.addWidget(self.rate_query)
        self.rate_apply=QtWidgets.QPushButton('应用采样率');self.rate_apply.setEnabled(False);self.rate_apply.clicked.connect(self.apply_rate);rate_bar.addWidget(self.rate_apply)
        self.rate_status=QtWidgets.QLabel('等待 MCU 查询结果；切换后需重新学习');self.rate_status.setWordWrap(True);rate_bar.addWidget(self.rate_status,1)
        self.cal_button=QtWidgets.QPushButton('六位置校准…');self.cal_button.clicked.connect(self.open_calibration);self.cal_button.setEnabled(False);rate_bar.addWidget(self.cal_button)
        xyz_box=QtWidgets.QWidget();xyz_layout=QtWidgets.QGridLayout(xyz_box)
        xyz_layout.setContentsMargins(0,0,0,0);xyz_layout.setHorizontalSpacing(12);xyz_layout.setVerticalSpacing(2)
        self.raw_xyz_cards=[];self.corrected_xyz_cards=[];self.xyz_titles=[]
        for row,(title,cards) in enumerate((('原始实际加速度 (mg)',self.raw_xyz_cards),('校准后加速度 (mg)',self.corrected_xyz_cards))):
            title_label=QtWidgets.QLabel(title);self.xyz_titles.append(title_label);xyz_layout.addWidget(title_label,row,0)
            for col,(axis,color) in enumerate(zip('XYZ',('#b42318','#127149','#1768b5')),1):
                label=QtWidgets.QLabel(axis+'  —');label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
                label.setStyleSheet(f'font-size:14px;color:{color};padding:2px 6px;background:#f1f5f9;border-radius:3px;')
                label.setToolTip('约0.5秒均值，包含重力；不是振动RMS或瞬时峰值。')
                xyz_layout.addWidget(label,row,col);xyz_layout.setColumnStretch(col,1);cards.append(label)
        self.xyz_cards=self.corrected_xyz_cards  # Compatibility with UI tests.
        self.raw_xyz_state=QtWidgets.QLabel('等待原始数据');xyz_layout.addWidget(self.raw_xyz_state,0,4)
        self.corrected_xyz_state=QtWidgets.QLabel('尚未确认校准');xyz_layout.addWidget(self.corrected_xyz_state,1,4)
        self.xyz_note=QtWidgets.QLabel('约0.5秒均值，含重力；校准后值仅采用MCU明确标记的结果。')
        self.xyz_note.setStyleSheet('font-size:11px;color:#667085;');xyz_layout.addWidget(self.xyz_note,2,0,1,3)
        self.firmware_label=QtWidgets.QLabel('MCU版本：等待核验');self.firmware_label.setStyleSheet('font-size:11px;')
        xyz_layout.addWidget(self.firmware_label,2,3,1,2)
        layout.addWidget(xyz_box)
        learning_box = QtWidgets.QGroupBox('MCU 本地正常状态学习'); layout.addWidget(learning_box)
        learning_layout = QtWidgets.QVBoxLayout(learning_box);learning_layout.setContentsMargins(6,4,6,4);learning_layout.setSpacing(3)
        learning_bar = QtWidgets.QHBoxLayout(); learning_layout.addLayout(learning_bar)
        self.learn = QtWidgets.QPushButton('学习正常状态（30秒）'); self.learn.clicked.connect(self.start_learning); learning_bar.addWidget(self.learn)
        self.cancel_learn = QtWidgets.QPushButton('取消学习'); self.cancel_learn.clicked.connect(lambda: self.learning_command('CANCEL')); learning_bar.addWidget(self.cancel_learn)
        status_cards=QtWidgets.QHBoxLayout();learning_layout.insertLayout(0,status_cards)
        self.detect_label = QtWidgets.QLabel('等待设备结果');self.detect_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter);self.detect_label.setMinimumHeight(76);status_cards.addWidget(self.detect_label,1)
        self.score_label = QtWidgets.QLabel('异常分数：—');self.score_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter);self.score_label.setMinimumHeight(76);status_cards.addWidget(self.score_label,1)
        self.paint_detection_state(None)
        learning_bar.addStretch()
        self.model_label = QtWidgets.QLabel('模型：未知'); learning_bar.addWidget(self.model_label)
        self.progress = QtWidgets.QProgressBar(); self.progress.setRange(0,100); self.progress.setValue(0); self.progress.setMaximumWidth(180); learning_bar.addWidget(self.progress)
        self.learning_note = QtWidgets.QLabel('固定安装并确认设备正常后学习；约1秒预热＋30秒有效数据。支持配套固件保存模型；是否保存成功以 MCU 存储结果为准。')
        self.learning_note.setWordWrap(True); learning_layout.addWidget(self.learning_note)
        self.learn.setEnabled(False); self.cancel_learn.setEnabled(False)
        fft_box = QtWidgets.QGroupBox('MCU FFT · 1024点 / Hann窗 / 峰值幅度');layout.addWidget(fft_box)
        fft_layout = QtWidgets.QVBoxLayout(fft_box)
        self.mcu_fft_label = QtWidgets.QLabel('等待 MCU FFT 结果');self.mcu_fft_label.setWordWrap(True);fft_layout.addWidget(self.mcu_fft_label)
        self.mcu_fft_status = QtWidgets.QLabel('以下频谱曲线由 PC 计算；两端 FFT 点数不同，主峰可能略有差异。');self.mcu_fft_status.setWordWrap(True);fft_layout.addWidget(self.mcu_fft_status)
        self.nvm_label = QtWidgets.QLabel('模型存储：等待 MCU 状态');self.nvm_label.setWordWrap(True);learning_layout.addWidget(self.nvm_label)
        controls = QtWidgets.QHBoxLayout(); layout.addLayout(controls)
        controls.addWidget(QtWidgets.QLabel('显示时长'))
        self.seconds = QtWidgets.QComboBox(); self.seconds.addItems(['0.1','0.2','0.5','1','2','4']); self.seconds.setCurrentText('0.2'); controls.addWidget(self.seconds)
        self.ac = QtWidgets.QCheckBox('去均值（观察微振动）'); self.ac.setChecked(True); controls.addWidget(self.ac)
        controls.addWidget(QtWidgets.QLabel('FFT 点数'))
        self.nfft = QtWidgets.QComboBox(); self.nfft.addItems(['1024','2048','4096','8192']); self.nfft.setCurrentText('4096'); controls.addWidget(self.nfft)
        self.axes = []
        for name, color in zip('XYZ', ['#ff6b6b','#4ddc98','#58b7ff']):
            cb = QtWidgets.QCheckBox(name); cb.setChecked(True); controls.addWidget(cb); self.axes.append(cb)
        controls.addStretch()
        view_controls = QtWidgets.QHBoxLayout(); layout.addLayout(view_controls)
        self.follow = QtWidgets.QCheckBox('跟随时间窗'); self.follow.setChecked(True); view_controls.addWidget(self.follow)
        self.auto_y = QtWidgets.QCheckBox('Y轴自动量程'); self.auto_y.setChecked(True); view_controls.addWidget(self.auto_y)
        restore = QtWidgets.QPushButton('恢复视图'); restore.clicked.connect(self.restore_view); view_controls.addWidget(restore)
        view_controls.addWidget(QtWidgets.QLabel('取消跟随后：滚轮缩放、左键拖动；频谱可独立缩放。'))
        view_controls.addStretch()
        self.metrics = QtWidgets.QLabel('等待数据；RMS/峰峰值基于所选显示窗口，去除均值。'); layout.addWidget(self.metrics)
        pg.setConfigOptions(antialias=False, background='#101923', foreground='#d5e4ee')
        self.wave = pg.PlotWidget(title='三轴加速度波形'); self.wave.setLabel('left','加速度',units='mg'); self.wave.setLabel('bottom','相对时间',units='s'); self.wave.showGrid(x=True,y=True,alpha=.2); self.wave.addLegend()
        self.wave.setMinimumHeight(120)
        self.fft = pg.PlotWidget(title='频谱（Hann 窗，去直流）'); self.fft.setLabel('left','幅值',units='mg'); self.fft.setLabel('bottom','频率',units='Hz'); self.fft.showGrid(x=True,y=True,alpha=.2); self.fft.addLegend()
        self.fft.setMinimumHeight(95)
        layout.addWidget(self.wave,3); layout.addWidget(self.fft,2)
        colors = ['#ff6b6b','#4ddc98','#58b7ff']
        self.curves = [self.wave.plot(pen=pg.mkPen(c,width=1),name=a) for a,c in zip('XYZ',colors)]
        for curve in self.curves:
            curve.setClipToView(True)
            curve.setDownsampling(auto=True,method="peak")
        self.spectra = [self.fft.plot(pen=c,name=a) for a,c in zip('XYZ',colors)]
        self.score_plot = pg.PlotWidget(title='MCU 异常分数（偏差指标，非故障概率；虚线为判断阈值）')
        self.score_plot.setLabel('left','异常分数'); self.score_plot.setLabel('bottom','相对时间',units='s')
        self.score_plot.setMinimumHeight(75); self.score_plot.setMaximumHeight(105)
        self.score_plot.showGrid(x=True,y=True,alpha=.2)
        self.score_curve = self.score_plot.plot(pen=pg.mkPen('#ffbf66',width=2))
        self.score_plot.addItem(pg.InfiniteLine(pos=4,angle=0,pen=pg.mkPen('#ff6b6b',style=QtCore.Qt.PenStyle.DashLine)))
        layout.addWidget(self.score_plot,1)
        self.perf_label=QtWidgets.QLabel('MCU 运行状态：等待上报（约5秒一次）');self.perf_label.setWordWrap(True)
        self.perf_label.setStyleSheet('font-size:11px;color:#667085;')
        self.perf_label.setToolTip('主循环忙碌率估计：扣除循环末尾HAL_Delay时间，包含SPI同步等待；不是精确CPU执行占用率。FFT/LCD为本统计周期的累计前台耗时，毫秒精度。队列峰值为本次启动累计值。')
        layout.addWidget(self.perf_label)
        self.status = QtWidgets.QLabel('未连接'); layout.addWidget(self.status)
        self.log = QtWidgets.QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(150); self.log.setMinimumHeight(38);self.log.setMaximumHeight(55); layout.addWidget(self.log)
        self.timer = QtCore.QTimer(self); self.timer.timeout.connect(self.update_data); self.timer.start(33)
        self.follow.toggled.connect(self.apply_view_mode)
        self.auto_y.toggled.connect(self.apply_view_mode)
        self.seconds.currentTextChanged.connect(self.apply_view_mode)
        self.apply_view_mode()
        self.refresh()
    def open_calibration(self):
        if self.record_path or self.rate_pending or self.pending_command or (self.last_detection and self.last_detection.state==1):
            QtWidgets.QMessageBox.information(self,'六位置校准','请先结束 CSV 保存、采样率切换或正常状态学习。');return
        self.calibration.query();self.cal_dialog.refresh();self.cal_dialog.show();self.cal_dialog.raise_()
    def update_calibration(self,w):
        if getattr(w,'is_h7',False):
            self.calibration.connection(False)
            self.firmware_label.setText('H743 USB FS · 当前应用数据协议')
            self.firmware_label.setStyleSheet('font-size:11px;color:#127149')
            self.xyz_titles[0].setText('USB 当前加速度 (mg)')
            self.xyz_titles[1].setText('独立校准回读 (mg)')
            if self.data and time.monotonic()-w.last_sample<2:
                values=np.mean(self.data.tail(max(1,self.fs//2)),axis=0)
                for a,label,v in zip('XYZ',self.raw_xyz_cards,values):label.setText(f'{a}  {v:+.3f}')
                self.raw_xyz_state.setText('设备数据 · 约0.5秒均值')
            else:
                for a,label in zip('XYZ',self.raw_xyz_cards):label.setText(a+'  —')
                self.raw_xyz_state.setText('等待USB数据')
            for a,label in zip('XYZ',self.corrected_xyz_cards):label.setText(a+'  —')
            self.corrected_xyz_state.setText('固件未独立上报')
            self.xyz_note.setText('沿用设备上传值与0.095换算；PC不附加校正。独立校准状态未知，不伪造两组值。')
            self.cal_button.setEnabled(False)
            self.cal_button.setToolTip('当前H743固件未提供旧校准对话框所需的完整确认协议。')
            self.record.setEnabled(w.connected and w.is_alive())
            return
        self.calibration.connection(w.connected and w.is_alive())
        while not w.cal_events.empty():self.calibration.event(w.cal_events.get_nowait())
        self.calibration.monitor(True)
        self.calibration.tick();self.cal_dialog.refresh()
        m=self.calibration
        self.firmware_label.setText(m.version_text());self.firmware_label.setStyleSheet('font-size:11px;color:'+('#127149' if m.link_ready else '#b42318'))
        if m.live_fresh():
            for a,label,v in zip('XYZ',self.raw_xyz_cards,m.live['mean']):label.setText(f'{a}  {v/1000:+.3f}')
            self.raw_xyz_state.setText('原始值 · 含零偏')
        else:
            for a,label in zip('XYZ',self.raw_xyz_cards):label.setText(a+'  —')
            self.raw_xyz_state.setText('未收到 / 超时')
        if m.actual_fresh() and m.actual['calibrated']:
            for a,label,v in zip('XYZ',self.corrected_xyz_cards,m.actual['mean']):label.setText(f'{a}  {v/1000:+.3f}')
            self.corrected_xyz_state.setText('已应用设备校准')
            self.xyz_note.setText('两行均为约0.5秒均值、含重力；校准后值已应用设备参数。')
        else:
            for a,label in zip('XYZ',self.corrected_xyz_cards):label.setText(a+'  —')
            if m.actual_fresh():
                self.corrected_xyz_state.setText('尚未校准')
                self.xyz_note.setText('请先完成六位置校准并保存；此处不把原始值当作校准后值。')
            else:
                self.corrected_xyz_state.setText('未收到 / 超时')
                self.xyz_note.setText('约0.5秒均值，含重力；两行分别以原始/已校准报文为准。')
        self.cal_button.setEnabled(w.connected and w.is_alive() and not getattr(w,'is_h7',False))
        if w.is_h7:self.cal_button.setToolTip('当前H743固件缺少旧版校准对话框需要的完整确认报文；暂不开放写入操作。')
        if self.calibration.locked:
            for button in (self.learn,self.cancel_learn,self.rate_apply,self.rate_combo,self.record):button.setEnabled(False)
        else:self.record.setEnabled(w.connected and w.is_alive())
    def paint_detection_state(self, state):
        # Color follows the confirmed MCU state, including alarm hold/recovery.
        bg,fg,border={
            0:('#eef2f6','#475467','#cbd5e1'),
            1:('#e5efff','#174ea6','#98b8f2'),
            2:('#e5efff','#174ea6','#98b8f2'),
            3:('#e0f4e9','#12613b','#7bc59c'),
            4:('#fff0c2','#915600','#e9b949'),
            5:('#ffe0df','#b42318','#ed8b85'),
        }.get(state,('#eef2f6','#667085','#cbd5e1'))
        common=f'background:{bg};color:{fg};border:2px solid {border};border-radius:8px;padding:10px;'
        self.detect_label.setStyleSheet(common+'font-size:28px;font-weight:700;')
        self.score_label.setStyleSheet(common+'font-size:32px;font-weight:700;')
    def apply_view_mode(self, *args):
        follow = self.follow.isChecked()
        self.wave.enableAutoRange(axis='x', enable=False)
        self.wave.setMouseEnabled(x=not follow, y=not self.auto_y.isChecked())
        self.wave.enableAutoRange(axis='y', enable=self.auto_y.isChecked())
        if follow:
            self.wave.setXRange(-float(self.seconds.currentText()), 0, padding=0)
    def restore_view(self):
        self.follow.setChecked(True); self.auto_y.setChecked(True)
        self.apply_view_mode()
        self.fft.enableAutoRange(axis='y', enable=True)
        self.fft.setXRange(0, self.fs/2, padding=0)
    def refresh(self):
        self.ports.clear()
        for p in list_ports.comports():
            self.ports.addItem(f'{p.device} · {p.description}',p.device)
            if 'STLink' not in p.description and 'CH343' not in p.description:self.ports.setCurrentIndex(self.ports.count()-1)
    def connect_port(self):
        if self.worker:
            self.worker.stop_event.set(); self.worker.join(2)
            if self.worker.is_alive(): self.log.appendPlainText('等待串口线程退出'); return
            self.worker = None; self.reset_detection(); self.record_path = None; self.record.setText('保存 CSV'); self.connect_button.setText('连接');self.baud.setEnabled(True); return
        if not self.ports.currentData():
            QtWidgets.QMessageBox.information(self,'串口','请先选择串口。'); return
        if any(x in self.ports.currentText() for x in ('CH343','STLink')):
            QtWidgets.QMessageBox.warning(self,'原生USB CDC','请选择MCU原生USB对应的USB串行设备，不是CH343或STLink。');return
        self.data.clear(); self.previous = None; self.gaps = 0
        self.reset_detection()
        self.worker = Receiver(self.ports.currentData(),int(self.baud.currentText()))
        self.rate_query_stamp=time.monotonic()
        self.baud.setEnabled(False)
        self.worker.start(); self.connect_button.setText('断开')
    def command(self, cmd):
        if self.worker and self.worker.is_alive():
            if cmd == 'START': self.data.clear(); self.previous = None
            self.worker.commands.put((cmd,None))
    def reset_detection(self):
        self.learning_tx.reset()
        self.calibration.connection(False);self.cal_dialog.refresh()
        for cards in (self.raw_xyz_cards,self.corrected_xyz_cards):
            for a,label in zip('XYZ',cards):label.setText(a+'  —')
        self.raw_xyz_state.setText('未连接');self.corrected_xyz_state.setText('未连接');self.firmware_label.setText('MCU版本：等待核验')
        self.xyz_note.setText('未连接')
        self.last_detection = None; self.detect_time = 0.0; self.pending_command = None
        self.perf_value=None;self.perf_stamp=0.0
        self.perf_label.setText('MCU 运行状态：等待上报（约5秒一次）');self.perf_label.setStyleSheet('font-size:11px;color:#667085;')
        self.rate_supported=();self.rate_pending=None;self.rate_query_stamp=None
        self.rate_combo.clear();self.rate_combo.addItem('等待 MCU 支持列表');self.rate_combo.setEnabled(False);self.rate_apply.setEnabled(False)
        self.rate_status.setText('等待 MCU 查询结果；切换后需重新学习')
        self.mcu_fft_value=None;self.mcu_fft_stamp=0.0;self.nvm_value=None;self.nvm_stamp=0.0
        self.mcu_fft_label.setText('等待 MCU FFT 结果');self.mcu_fft_status.setText('MCU FFT 未连接')
        self.nvm_label.setText('模型存储：等待 MCU 状态')
        self.scores.clear(); self.score_curve.clear(); self.progress.setValue(0)
        self.detect_label.setText('等待设备结果'); self.paint_detection_state(None)
        self.score_label.setText('异常分数：—'); self.model_label.setText('模型：未知')
        self.learn.setEnabled(False); self.cancel_learn.setEnabled(False)
    def start_learning(self):
        self.learning_command('LEARN')
    def learning_command(self, cmd):
        if cmd=='CANCEL' and self.worker and getattr(self.worker,'is_h7',False):
            self.learning_note.setText('当前H743固件未实现CANCEL，未发送取消指令。');return
        if self.calibration.locked:
            self.learning_note.setText('校准会话或校准操作尚未结束，请先完成或取消校准。');return
        if self.rate_pending:
            self.learning_note.setText('正在切换采样率，请等待完成。');return
        if not self.worker or not self.worker.connected or not self.worker.is_alive():
            self.learning_note.setText('串口未连接，学习指令未发送。');return
        if self.learning_tx.request(cmd):
            self.pending_command=self.learning_tx.pending
            self.learning_note.setText(self.learning_tx.note)
            self.learn.setEnabled(False);self.cancel_learn.setEnabled(True)
    def update_detection(self, worker):
        now = time.monotonic()
        while not worker.learning_events.empty():
            stamp,event=worker.learning_events.get_nowait();self.learning_tx.event(stamp,event)
        while not worker.detections.empty():
            stamp,d = worker.detections.get_nowait()
            self.detect_time = stamp; self.last_detection = d
            self.scores.append((stamp,d.score))
            was_starting=self.learning_tx.cmd=='LEARN'
            self.learning_tx.observe(stamp,d.state)
            if was_starting and not self.learning_tx.pending and d.state==1:
                self.command('START')  # Upload only AFTER the MCU confirms local learning.

        connected = worker.connected and worker.is_alive()
        self.learning_tx.tick(connected);self.pending_command=self.learning_tx.pending
        fresh = connected and self.last_detection is not None and now-self.detect_time<3.5
        self.learn.setEnabled(connected and not self.pending_command and not (fresh and self.last_detection.state==1))
        self.cancel_learn.setEnabled(connected and not getattr(worker,'is_h7',False) and ((fresh and self.last_detection.state==1) or bool(self.pending_command)))
        if not fresh:
            self.detect_label.setText('结果超时' if self.last_detection else '等待设备结果')
            self.paint_detection_state(None)
            self.score_label.setText('异常分数：—'); self.model_label.setText('模型：未知（无最新结果）')
        else:
            d = self.last_detection
            self.detect_label.setText(STATES[d.state])
            self.paint_detection_state(d.state)
            self.score_label.setText(f'异常分数：{d.score:.2f}')
            self.model_label.setText('模型：已建立（MCU）' if d.model else '模型：未建立')
            self.progress.setValue(d.progress)
            if not self.pending_command and now>=self.learning_tx.notice_until:
                note = '学习中，请保持固定安装和正常运行。' if d.state==1 else '检测在 MCU 本地执行；超过阈值需连续5个窗口才报警，恢复也需连续正常窗口。'
                self.learning_note.setText(note+' 当前分数不是故障概率；报警与恢复均有连续窗口确认。')
        if self.pending_command or now<self.learning_tx.notice_until:
            self.learning_note.setText(self.learning_tx.note)
        if self.scores:
            stamps,values = zip(*self.scores)
            # A telemetry outage breaks the curve instead of implying continuous results.
            xx=[]; yy=[]
            for i,(stamp,value) in enumerate(zip(stamps,values)):
                if i and stamp-stamps[i-1]>3.5: xx.append(stamp-now); yy.append(float('nan'))
                xx.append(stamp-now); yy.append(value)
            self.score_curve.setData(xx,yy,connect='finite')
            self.score_plot.setXRange(-60,0,padding=0)
    def query_rate(self):
        if self.worker and self.worker.connected and self.worker.is_alive() and not self.rate_pending:
            self.command('RATE?');self.rate_query_stamp=time.monotonic()
            self.rate_status.setText('正在查询 MCU 实际采样率及支持档位…')
    def apply_rate(self):
        if self.calibration.locked:return
        w=self.worker;target=self.rate_combo.currentData()
        if not w or not w.connected or not w.is_alive() or self.rate_pending or self.record_path:return
        if target not in self.rate_supported:return
        if self.last_detection and self.last_detection.state==1:return
        self.command(f'RATE {target}');self.rate_pending=(target,time.monotonic())
        self.rate_status.setText(f'已请求 {target} Hz，等待 MCU 确认；原学习模型需重新学习')
        self.rate_apply.setEnabled(False)
    def update_rate(self, w):
        now=time.monotonic();connected=w.connected and w.is_alive()
        while not w.rate_events.empty():
            stamp,(kind,v)=w.rate_events.get_nowait()
            if kind=='caps':
                self.rate_supported=v['supported'];self.rate_combo.clear()
                for rate in self.rate_supported:self.rate_combo.addItem(f'{rate} Hz',rate)
                self.rate_combo.setCurrentIndex(self.rate_supported.index(v['current']))
                self.rate_query_stamp=None
                self.rate_status.setText(f"MCU 当前 {v['current']} Hz；切换成功后需重新学习。")
            elif kind=='ack' and self.rate_pending and stamp>=self.rate_pending[1]:
                target,_=self.rate_pending
                if v['current']!=target:
                    self.rate_status.setText(f"确认速率不匹配：请求 {target} Hz，设备返回 {v['current']} Hz；请重新查询。")
                    self.rate_supported=()
                else:
                    # ACK confirms sensor rate, not validity of the previous learned model.
                    self.fs=target;self.data.clear();self.previous=None
                    while not w.packets.empty():w.packets.get_nowait()
                    for c in self.curves+self.spectra:c.clear()
                    self.last_fft=0;self.last_detection=None;self.detect_time=0
                    self.scores.clear();self.score_curve.clear()
                    self.mcu_fft_value=None;self.mcu_fft_stamp=0;self.nvm_value=None;self.nvm_stamp=0
                    self.fft.setXRange(0,target/2,padding=0)
                    self.rate_status.setText(f'已确认切换为 {target} Hz；连续数据缓存已清空，请重新学习。')
                self.rate_pending=None
            elif kind=='error':
                self.rate_pending=None;self.rate_query_stamp=None
                self.rate_status.setText('MCU 采样率操作失败：'+v['reason'])
        if self.rate_pending and now-self.rate_pending[1]>=5:
            self.rate_pending=None;self.rate_supported=()
            self.rate_status.setText('切换未收到确认，实际速率未知；请重新查询，界面未假定切换成功。')
        if self.rate_query_stamp and now-self.rate_query_stamp>=5:
            self.rate_query_stamp=None
            self.rate_status.setText('未收到采样率能力回复：当前固件可能尚不支持 RATE 指令。原有采集可继续。')
        self.rate_query.setEnabled(connected and not self.rate_pending)
        self.rate_combo.setEnabled(connected and bool(self.rate_supported) and not self.rate_pending)
        learning=self.last_detection is not None and self.last_detection.state==1
        self.rate_apply.setEnabled(connected and bool(self.rate_supported) and not self.rate_pending and not learning and not self.record_path)
    def update_mcu_telemetry(self, worker):
        now=time.monotonic()
        while not worker.telemetry.empty():
            stamp,(kind,value)=worker.telemetry.get_nowait()
            if kind=='perf':self.perf_stamp=stamp;self.perf_value=value
            elif kind=='fft':self.mcu_fft_stamp=stamp;self.mcu_fft_value=value
            elif kind=='nvm':self.nvm_stamp=stamp;self.nvm_value=value
            elif kind=='save':
                # Periodic NVM status will confirm this event; count=0 is never success.
                self.nvm_stamp=stamp
                self.nvm_value=dict(init=0,load=0,save=value['save'],count=value['count'],seq=value['seq'])
            elif kind=='h7fifo':self.perf_stamp=stamp;self.perf_value=dict(h7=True,**value)
            elif kind=='h7nvm':self.nvm_stamp=stamp;self.nvm_value=dict(h7=True,**value)
            elif kind=='h7save':self.nvm_stamp=stamp;self.nvm_value=dict(h7=True,**value)
        connected=worker.connected and worker.is_alive()
        perf=self.perf_value
        if not connected or perf is None or now-self.perf_stamp>12:
            self.perf_label.setText('MCU 运行状态：上报超时' if perf else 'MCU 运行状态：等待上报（约5秒一次）')
            self.perf_label.setStyleSheet('font-size:11px;color:#667085;')
        elif perf.get('h7'):
            self.perf_label.setText(f"FIFO {perf['rate']}点/s · level={perf['level']} · 溢出 {perf['overrun']} · 读取错误 {perf['errors']} · LCD {perf['lcd']} / {perf['fps']}fps · TX丢弃 {perf['txdrop']} · 上传丢帧 {perf['streamdrop']}")
            self.perf_label.setStyleSheet('font-size:11px;color:#16834b;')
        else:
            self.perf_label.setText(f"MCU 忙碌≈{perf['busy']/10:.1f}%  |  FFT调度 {perf['fft']} ms / {perf['period']/1000:.1f}s  |  LCD {perf['lcd']} ms，最长 {perf['lcd_max']} ms，{perf['fps']/10:.1f} FPS  |  TX队列 {perf['q']}/{perf['qcap']}，峰值 {perf['qmax']}")
            color='#b42318' if perf['busy']>=950 or perf['q']*100>=perf['qcap']*90 else '#915600' if perf['busy']>=800 or perf['q']*100>=perf['qcap']*75 else '#16834b'
            self.perf_label.setStyleSheet('font-size:11px;color:'+color+';')
        f=self.mcu_fft_value
        if not connected or f is None or now-self.mcu_fft_stamp>=3.5:
            self.mcu_fft_label.setText('MCU FFT：结果超时' if f else 'MCU FFT：等待设备结果')
            self.mcu_fft_status.setText('以下频谱由 PC 计算；暂无有效 MCU FFT 结果。')
        elif not f['valid']:
            self.mcu_fft_label.setText('MCU FFT：等待完整连续数据窗口')
            self.mcu_fft_status.setText(f"已完成 {f['windows']} 组 · 跳过 {f['skip']} 个分析窗口")
        else:
            self.mcu_fft_label.setText('    |    '.join(f"{a}：{hz:.2f} Hz / {amp:.2f} mg" for a,hz,amp in zip('XYZ',f['hz'],f['amp'])))
            if f['age'] is None:
                self.mcu_fft_status.setText(f"已完成 {f['windows']} 组 · 跳过 {f['skip']} · H743未上报结果年龄/调度时长；幅值为峰值，非RMS。")
            else:self.mcu_fft_status.setText(f"已完成 {f['windows']} 组 · 跳过 {f['skip']} · 发布后样本时间 {f['age']} ms · 调度批次最大 {f['step']} ms；幅值为峰值，非 RMS。" + (' 【结果超过1秒未更新】' if f['age']>1000 else ''))
        n=self.nvm_value
        if not connected or n is None or now-self.nvm_stamp>=3.5:
            self.nvm_label.setText('模型存储：状态超时' if n else '模型存储：等待 MCU 状态')
        elif n.get('h7'):
            if 'restart' in n:self.nvm_label.setText(f"H743模型保存：返回 {n['save']} · 采集重启 {n['restart']} · 模型位图 {n['models']}（0表示该步成功）")
            else:
                code=n['code'];note='存在有效记录 / 最近操作成功' if code==0 else '无有效保存记录' if code==1 else f'返回错误 {code}'
                self.nvm_label.setText('H743模型存储：'+note+'；此报文未提供启动恢复次数或Flash序号。')
        elif n['init']!=0:self.nvm_label.setText(f"模型存储：初始化失败 {n['init']}")
        else:
            loaded='本次启动已从 Flash 恢复模型' if n['load']==1 else '本次启动未恢复模型' if n['load']==0 else f"启动加载失败 {n['load']}"
            saved=f"本次启动已成功保存 {n['count']} 次" if n['count'] else '本次启动尚无成功保存'
            if n['save']!=0:saved+=f"；最近保存错误 {n['save']}"
            self.nvm_label.setText(f"模型存储：{loaded}；{saved}；Flash 序号 {n['seq']}。")
    def toggle_record(self):
        if self.calibration.locked:return
        if not self.worker or not self.worker.is_alive(): return
        if self.record_path:
            self.worker.commands.put(('record',None)); self.record_path = None; self.record.setText('保存 CSV')
        else:
            path,_ = QtWidgets.QFileDialog.getSaveFileName(self,'保存完整原始采样','vibration.csv','CSV (*.csv)')
            if path:
                self.record_path = path; self.worker.commands.put(('record',path)); self.record.setText('结束保存')
    def update_data(self):
        w = self.worker
        if not w: return
        log_batch=[]
        for _ in range(64):
            try: log_batch.append(w.logs.get_nowait())
            except queue.Empty: break
        if log_batch: self.log.appendPlainText("\n".join(log_batch))
        self.update_rate(w)
        self.update_mcu_telemetry(w)
        self.update_detection(w)
        self.update_calibration(w)
        if self.rate_pending:
            self.learn.setEnabled(False);self.cancel_learn.setEnabled(False)
        changed = False
        deadline=time.monotonic()+.008
        for _ in range(256):
            if time.monotonic()>=deadline: break
            try: seq,fs,first,flags,raw = w.packets.get_nowait()
            except queue.Empty: break
            expected = self.previous
            if flags or fs != self.fs or (expected and (seq != expected[0] or first != expected[1])):
                self.data.clear(); self.gaps += 1
            self.fs = fs
            self.previous = ((seq+1)&0xffffffff,(first+len(raw))&0xffffffff)
            self.data.extend(raw*.095); changed = True
        state = ('接收中' if time.monotonic()-w.last_sample<2 else '已连接，等待采样数据') if w.is_alive() else '连接已结束，请断开后重连'
        self.status.setText(f'{state} | USB CDC ({w.port}) | Fs={self.fs} Hz | 样本 {w.received} | CRC/格式错误 {w.parser.errors} | 接收断点 {w.continuity.events}（序号{w.continuity.counts["seq"]}/索引{w.continuity.counts["index"]}/标志{w.continuity.counts["flags"]}/速率{w.continuity.counts["rate"]}）| 显示断点 {self.gaps} | 显示队列丢帧 {w.drops} | CSV {w.recorded} 点')
        if not changed or len(self.data)<8: return
        count = max(8,int(float(self.seconds.currentText())*self.fs))
        all_data = self.data.tail(max(count,int(self.nfft.currentText())))
        y = all_data[-count:]; ac = y-y.mean(axis=0)
        shown = ac if self.ac.isChecked() else y
        x = (np.arange(len(y))-len(y)+1)/self.fs
        for a,curve in enumerate(self.curves):
            curve.setVisible(self.axes[a].isChecked()); curve.setData(x,shown[:,a])
        if self.follow.isChecked():
            self.wave.setXRange(-float(self.seconds.currentText()), 0, padding=0)
        rms = np.sqrt(np.mean(ac*ac,axis=0)); pp = np.ptp(ac,axis=0)
        metrics = '    '.join(f'{axis}: RMS {r:.3f} / P-P {p:.3f} mg' for axis,r,p in zip('XYZ',rms,pp))
        self.metrics.setText(metrics)
        if time.monotonic()-self.last_fft < .15: return
        self.last_fft = time.monotonic()
        n = int(self.nfft.currentText())
        if len(all_data)<n:
            self.fft.setTitle(f'FFT 等待连续数据 {len(all_data)}/{n}')
            for c in self.spectra: c.clear()
            return
        f,amp = spectrum(all_data[-n:],self.fs)
        peaks = []
        for a,c in enumerate(self.spectra):
            c.setVisible(self.axes[a].isChecked()); c.setData(f,amp[:,a])
            peak = 1+int(np.argmax(amp[1:,a])); peaks.append(f'{"XYZ"[a]} {f[peak]:.2f} Hz')
        self.fft.setTitle(f'PC 主峰: {" / ".join(peaks)} · Δf={self.fs/n:.3f} Hz')
    def closeEvent(self,event):
        if self.calibration.locked:
            self.calibration.note='退出前请先取消校准；保存过程中请等待最终确认。'
            self.cal_dialog.refresh();self.cal_dialog.show();event.ignore();return
        if self.worker:
            self.worker.stop_event.set(); self.worker.join(2)
            if self.worker.is_alive(): event.ignore(); return
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = Window(); window.show()
    sys.exit(app.exec())
