from PySide6 import QtCore, QtWidgets, QtGui
from calibration import FACES
from i18n import translate_text, translate_widget_tree

class CalibrationDialog(QtWidgets.QDialog):
    def __init__(self,model,parent=None):
        super().__init__(parent);self.model=model;self._last_mask=None;self._last_check=None
        self._title_zh='六位置校准 · MCU 参数保存'
        self._headers_zh=['朝上方向','原始 X (mg)','原始 Y (mg)','原始 Z (mg)','校正残差 X / Y / Z (mg)','结果']
        self.setWindowTitle(self._title_zh);self.resize(1150,820)
        layout=QtWidgets.QVBoxLayout(self)
        intro=QtWidgets.QLabel('停机后操作：依次让 X+、X−、Y+、Y−、Z+、Z− 朝上。每面放稳后采集 5 秒，收到完成结果再换面。\n校准由 MCU 计算和应用；本软件不会对收到的数据重复校正。')
        intro.setWordWrap(True);layout.addWidget(intro)
        live_box=QtWidgets.QGroupBox('未校准三轴读数 · 约0.5秒均值');live_layout=QtWidgets.QVBoxLayout(live_box)
        cards=QtWidgets.QHBoxLayout();self.live_cards=[]
        for axis,color in zip('XYZ',('#b42318','#127149','#1768b5')):
            card=QtWidgets.QLabel(axis+'  — mg');card.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            card.setStyleSheet(f'font-size:23px;font-weight:600;color:{color};background:#f1f5f9;padding:12px;border-radius:5px;')
            self.live_cards.append(card);cards.addWidget(card)
        live_layout.addLayout(cards)
        self.live_state=QtWidgets.QLabel('等待实时数据');self.live_state.setWordWrap(True);live_layout.addWidget(self.live_state)
        raw_note=QtWidgets.QLabel('这些数值包含重力和零偏；校准前不要求某轴恰好为±1000 mg、其余轴为0。请按传感器轴向标识摆放。')
        raw_note.setWordWrap(True);live_layout.addWidget(raw_note);layout.addWidget(live_box)
        top=QtWidgets.QHBoxLayout();layout.addLayout(top)
        self.begin=QtWidgets.QPushButton('开始新校准');self.begin.clicked.connect(lambda:self.request('begin'));top.addWidget(self.begin)
        self.query=QtWidgets.QPushButton('查询设备状态');self.query.clicked.connect(self.query_all);top.addWidget(self.query)
        self.cancel=QtWidgets.QPushButton('取消本次校准');self.cancel.clicked.connect(lambda:self.request('cancel'));top.addWidget(self.cancel)
        self.version_label=QtWidgets.QLabel();self.version_label.setWordWrap(True);layout.addWidget(self.version_label)
        self.table=QtWidgets.QTableWidget(6,6);self.table.setHorizontalHeaderLabels(self._headers_zh)
        self.table.verticalHeader().hide();self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        for i,f in enumerate(FACES):
            for j,t in enumerate((f,f'{f[0]} 轴{ "正" if i%2==0 else "负" }方向朝上','待采集')):
                self.table.setItem(i,j,QtWidgets.QTableWidgetItem(t))
        self.table.horizontalHeader().setSectionResizeMode(0,QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0,70)
        self.table.horizontalHeader().setSectionResizeMode(4,QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4,320)
        self.table.horizontalHeader().setSectionResizeMode(5,QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5,100)
        for i in range(6):
            for j in range(6):self.table.setItem(i,j,QtWidgets.QTableWidgetItem('—'))
            self.table.item(i,0).setText(FACES[i])
            self.table.item(i,0).setToolTip(f'{FACES[i]} 对应传感器 {FACES[i][0]} 轴'+('正' if i%2==0 else '负')+'方向朝上')
        self.table.selectRow(0);layout.addWidget(self.table)
        self.capture=QtWidgets.QPushButton('采集所选面（5秒）');self.capture.clicked.connect(self.capture_face);layout.addWidget(self.capture)
        self.progress=QtWidgets.QProgressBar();layout.addWidget(self.progress)
        self.mean=QtWidgets.QLabel('本面原始均值：—');layout.addWidget(self.mean)
        self.solve=QtWidgets.QPushButton('计算并检查六面结果');self.solve.clicked.connect(lambda:self.request('solve'));layout.addWidget(self.solve)
        self.quality_label=QtWidgets.QLabel('零偏/比例：待求解；综合一致性：待核验。旁轴残差为姿态提示。')
        self.quality_label.setWordWrap(True);layout.addWidget(self.quality_label)
        self.params=QtWidgets.QLabel();self.params.setWordWrap(True);layout.addWidget(self.params)
        self.save=QtWidgets.QPushButton('写入设备并清除旧学习模型');self.save.clicked.connect(lambda:self.request('save'));layout.addWidget(self.save)
        self.note=QtWidgets.QLabel();self.note.setWordWrap(True)
        self.note.setMinimumHeight(55);self.note.setStyleSheet('background:#edf3fa;padding:10px;border-radius:6px;');layout.addWidget(self.note)
        foot=QtWidgets.QLabel('保存后需在正常运行工况下重新学习。六面校准不替代高频振动幅值/频响校验。')
        foot.setWordWrap(True);layout.addWidget(foot)
        self.refresh()
    def apply_language(self, language='zh'):
        translate_widget_tree(self, language)
        self.setWindowTitle(translate_text(self._title_zh, language))
        self.table.setHorizontalHeaderLabels([translate_text(value, language) for value in self._headers_zh])

    def query_all(self):
        self.model.query_info();self.model.query();self.model.query_data()
    def request(self,kind):
        if self.model.request(kind):self.refresh()
    def capture_face(self):
        row=self.table.currentRow()
        if self.model.request('face',row):self.refresh()
    def refresh(self):
        m=self.model;idle=m.connected and m.known and not m.pending and not m.remote_pending and not m.uncertain
        if m.live_fresh():
            for axis,card,value in zip('XYZ',self.live_cards,m.live['mean']):card.setText(f'{axis}  {value/1000:+.3f} mg')
            status='静止（仍需保持到本面采集结束）' if m.live['stable'] else '检测到运动 / 振动，请放稳'
            self.live_state.setText(status+'  |  标准差 X/Y/Z：'+', '.join(f'{v/1000:.3f}' for v in m.live['std'])+' mg')
            self.live_state.setStyleSheet('color:'+('#127149' if m.live['stable'] else '#b42318'))
        else:
            for axis,card in zip('XYZ',self.live_cards):card.setText(axis+'  — mg')
            self.live_state.setText('实时数据未到达或已超时；需配套 MCU_Calibration_V1_4，且无需点击“开始采集”。')
            self.live_state.setStyleSheet('color:#667085')
        self.version_label.setText(m.version_text());self.version_label.setStyleSheet('color:'+('#127149' if m.link_ready else '#b42318'))
        self.begin.setEnabled(idle and m.link_ready and not m.session)
        self.capture.setEnabled(idle and m.link_ready and m.session and m.face<0)
        self.solve.setEnabled(idle and m.link_ready and m.session and m.face<0 and m.mask==63)
        self.save.setEnabled(idle and m.link_ready and m.session and m.solved and bool(m.candidate))
        self.cancel.setEnabled(m.connected and (m.session or bool(m.pending)) and m.pending not in ('save','verify','cancel') and not m.remote_pending)
        self.query.setEnabled(m.connected)
        for i in range(6):
            row=m.rows.get(i);valid=bool(m.mask&(1<<i));checked=valid and row and row['checked']
            failed=bool(checked and any(abs(v)>50000 for v in row['residual']))
            hard_fail=bool(checked and m.quality and (abs(m.quality['norm'][i])>50000 or m.quality['pair'][i//2]>50000))
            for j in range(1,4):self.table.item(i,j).setText(f"{row['raw'][j-1]/1000:+.3f}" if valid and row and row['valid'] else '—')
            self.table.item(i,4).setText(' / '.join(f'{v/1000:+.2f}' for v in row['residual']) if checked else '待求解核验')
            self.table.item(i,5).setText('采集中…' if m.face==i else '一致性超限' if hard_fail else '姿态提示' if failed else '已核验' if checked else ('已采集' if row and row['valid'] else '明细待返回') if valid else '待采集')
            for j in (4,5):self.table.item(i,j).setBackground(QtGui.QColor('#ffe0df' if hard_fail else '#fff0c2' if failed else '#e0f4e9' if checked else '#ffffff'))
        selected=self.table.currentRow()
        self.capture.setText(('重采所选面' if selected>=0 and m.mask&(1<<selected) else '采集所选面')+'（5秒，其余面保留）')
        check_key=tuple(m.check.values()) if m.check else None
        if check_key!=self._last_check:
            if m.check and m.quality and m.check['rc']==-4:self.table.selectRow(max(range(6),key=lambda i:abs(m.quality['norm'][i])))
            elif m.check and m.quality and m.check['rc']==-5:self.table.selectRow(2*max(range(3),key=lambda i:m.quality['pair'][i]))
            self._last_check=check_key
        if m.mask!=self._last_mask and m.face<0 and not m.pending:
            if m.mask!=63:self.table.selectRow(next(i for i in range(6) if not m.mask&(1<<i)))
            self._last_mask=m.mask
        self.progress.setValue(min(100,int(100*m.samples/m.target)) if m.face>=0 and m.target else int(m.mask.bit_count()/6*100))
        self.progress.setFormat('本面采集 %p%' if m.face>=0 else f'已采集 {m.mask.bit_count()}/6 面')
        if m.last_mean:self.mean.setText('最近一面原始均值：'+' / '.join(f'{a} {v/1000:.3f} mg' for a,v in zip('XYZ',m.last_mean)))
        def describe(p):
            return '零偏 '+', '.join(f'{v/1000:.3f}' for v in p['offset'])+' mg；比例 '+', '.join(f'{v/1000000:.6f}' for v in p['gain'])
        lines=['当前设备参数：'+describe(m.active)+('（已校准）' if m.active['valid'] else '（默认值，尚未校准）')] if m.active else ['当前设备参数：等待查询']
        if m.candidate:lines.append('本次候选参数：'+describe(m.candidate))
        if m.quality and m.check and m.check['rc'] in (0,-4,-5):
            self.quality_label.setText(('零偏/比例：通过；综合一致性：'+('通过' if m.check['rc']==0 else '未通过'))+
                '\n六面合量相对1g偏差 (mg)：'+', '.join(f'{v/1000:+.2f}' for v in m.quality['norm'])+
                '\nX/Y/Z 正反面对称性偏差 (mg)：'+', '.join(f'{v/1000:.2f}' for v in m.quality['pair'])+'。旁轴残差>50 mg仅为黄色姿态提示。')
        else:self.quality_label.setText('零偏/比例及综合一致性：待完成六面求解。旁轴残差为姿态提示。')
        self.params.setText('\n'.join(lines));self.note.setText(m.note)
    def showEvent(self,event):
        self.model.monitor(True);super().showEvent(event)
    def hideEvent(self,event):
        super().hideEvent(event)  # Main XYZ preview remains active while connected.
    def closeEvent(self,event):
        m=self.model
        if m.connected and (m.session or m.pending or m.remote_pending):
            m.note='校准尚未结束，请先点“取消本次校准”；保存过程中请等待最终确认。'
            self.refresh();event.ignore()
        else:event.accept()
