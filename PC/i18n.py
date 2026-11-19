"""Lightweight Chinese/English UI translation for the H743 vibration monitor."""
import re
from functools import lru_cache
# Keep Chinese as the source language so existing tests and default behavior stay unchanged.
ZH_EN = {
    # Main window and toolbar
    '三轴振动监测 · H743 USB FS · 40/80K试验版': '3-Axis Vibration Monitor · H743 USB FS · 40/80K Test',
    '语言 / Language': 'Language', '中文': '中文', 'English': 'English',
    '刷新串口': 'Refresh Ports', '连接': 'Connect', '断开': 'Disconnect',
    '开始采集': 'Start Acquisition', '停止采集': 'Stop Acquisition',
    '保存 CSV': 'Save CSV', '结束保存': 'Stop Saving',
    '传感器采样率': 'Sensor ODR', '等待 MCU 支持列表': 'Waiting for MCU supported rates',
    '查询采样率': 'Query ODR', '应用采样率': 'Apply ODR',
    '等待 MCU 查询结果；切换后需重新学习': 'Waiting for MCU response; retraining is required after changing ODR',
    '六位置校准…': 'Six-Position Calibration…',
    '原始实际加速度 (mg)': 'Raw Acceleration (mg)',
    '校准后加速度 (mg)': 'Calibrated Acceleration (mg)',
    '等待原始数据': 'Waiting for raw data', '尚未确认校准': 'Calibration not verified',
    'MCU版本：等待核验': 'MCU version: verification pending',
    'MCU 本地正常状态学习': 'MCU On-Device Normal-State Learning',
    '学习正常状态（30秒）': 'Learn Normal State (30 s)', '取消学习': 'Cancel Learning',
    '等待设备结果': 'Waiting for device result', '异常分数：—': 'Anomaly Score: —',
    '模型：未知': 'Model: Unknown', 'MCU FFT · 1024点 / Hann窗 / 峰值幅度': 'MCU FFT · 1024 points / Hann Window / Peak Amplitude',
    '等待 MCU FFT 结果': 'Waiting for MCU FFT result',
    '以下频谱曲线由 PC 计算；两端 FFT 点数不同，主峰可能略有差异。': 'The spectrum below is calculated by the PC. Different FFT sizes may cause slight differences in peak frequency.',
    '模型存储：等待 MCU 状态': 'Model Storage: Waiting for MCU status',
    '显示时长': 'Time Span', '去均值（观察微振动）': 'Remove Mean (View Micro-vibration)',
    'FFT 点数': 'FFT Size', '跟随时间窗': 'Follow Time Window', 'Y轴自动量程': 'Auto Y Scale',
    '恢复视图': 'Reset View',
    '取消跟随后：滚轮缩放、左键拖动；频谱可独立缩放。': 'When follow mode is off: use the wheel to zoom and drag with the left mouse button. The spectrum can be zoomed independently.',
    '等待数据；RMS/峰峰值基于所选显示窗口，去除均值。': 'Waiting for data; RMS and peak-to-peak values use the selected display window with the mean removed.',
    '三轴加速度波形': '3-Axis Acceleration Waveform', '加速度': 'Acceleration',
    '相对时间': 'Relative Time', '频谱（Hann 窗，去直流）': 'Spectrum (Hann Window, DC Removed)',
    '幅值': 'Amplitude', '频率': 'Frequency',
    'MCU 异常分数（偏差指标，非故障概率；虚线为判断阈值）': 'MCU Anomaly Score (Deviation Metric, Not Failure Probability; Dashed Line = Threshold)',
    '异常分数': 'Anomaly Score', 'MCU 运行状态：等待上报（约5秒一次）': 'MCU Runtime: Waiting for telemetry (about every 5 s)',
    '未连接': 'Disconnected',
    # Tooltips and fixed descriptions
    '原生USB CDC不受此波特率限制；当前默认115200。': 'Native USB CDC is not limited by this baud-rate setting; the default is 115200.',
    '约0.5秒均值，包含重力；不是振动RMS或瞬时峰值。': 'Approx. 0.5 s mean including gravity; this is not vibration RMS or an instantaneous peak.',
    '约0.5秒均值，含重力；校准后值仅采用MCU明确标记的结果。': 'Approx. 0.5 s mean including gravity. Calibrated values are shown only when explicitly reported by the MCU.',
    '主循环忙碌率估计：扣除循环末尾HAL_Delay时间，包含SPI同步等待；不是精确CPU执行占用率。FFT/LCD为本统计周期的累计前台耗时，毫秒精度。队列峰值为本次启动累计值。': 'Main-loop busy estimate: excludes the trailing HAL_Delay and includes synchronous SPI waits; it is not an exact CPU utilization measurement. FFT/LCD values are accumulated foreground time for this interval (ms). Queue peak is accumulated since startup.',
    # Calibration / XYZ states
    '等待原始数据': 'Waiting for raw data', '等待USB数据': 'Waiting for USB data',
    '设备数据 · 约0.5秒均值': 'Device data · approx. 0.5 s mean',
    '固件未独立上报': 'Firmware does not report this independently',
    '沿用设备上传值与0.095换算；PC不附加校正。独立校准状态未知，不伪造两组值。': 'Uses device-reported values with the 0.095 conversion; no additional PC-side correction is applied. Independent calibration status is unknown, so no calibrated values are fabricated.',
    '原始值 · 含零偏': 'Raw values · offset included', '未收到 / 超时': 'Not received / Timeout',
    '已应用设备校准': 'Device calibration applied',
    '两行均为约0.5秒均值、含重力；校准后值已应用设备参数。': 'Both rows show approx. 0.5 s means including gravity; device calibration parameters are applied to the calibrated values.',
    '尚未校准': 'Not calibrated',
    '请先完成六位置校准并保存；此处不把原始值当作校准后值。': 'Complete and save the six-position calibration first. Raw values are not presented as calibrated values.',
    '约0.5秒均值，含重力；两行分别以原始/已校准报文为准。': 'Approx. 0.5 s mean including gravity; each row follows the raw/calibrated data reported by the device.',
    'H743 USB FS · 当前应用数据协议': 'H743 USB FS · Current application data protocol',
    'USB 当前加速度 (mg)': 'USB Current Acceleration (mg)', '独立校准回读 (mg)': 'Calibration Readback (mg)',
    '未连接': 'Disconnected',
    # Learning and connection messages
    '固定安装并确认设备正常后学习；约1秒预热＋30秒有效数据。支持配套固件保存模型；是否保存成功以 MCU 存储结果为准。': 'Keep the device firmly mounted and verify normal operation before learning. Allow approx. 1 s warm-up plus 30 s of valid data. Model saving requires compatible firmware; MCU storage status is authoritative.',
    '当前H743固件未实现CANCEL，未发送取消指令。': 'The current H743 firmware does not implement CANCEL. No cancel command was sent.',
    '校准会话或校准操作尚未结束，请先完成或取消校准。': 'A calibration session or operation is still active. Complete or cancel calibration first.',
    '正在切换采样率，请等待完成。': 'ODR change in progress. Please wait.',
    '串口未连接，学习指令未发送。': 'Serial port is not connected. The learning command was not sent.',
    '学习中，请保持固定安装和正常运行。': 'Learning in progress. Keep the device firmly mounted and operating normally.',
    '检测在 MCU 本地执行；超过阈值需连续5个窗口才报警，恢复也需连续正常窗口。': 'Detection runs on the MCU. An alarm requires five consecutive windows above the threshold; recovery also requires consecutive normal windows.',
    '当前分数不是故障概率；报警与恢复均有连续窗口确认。': 'The current score is not a failure probability. Both alarms and recovery require confirmation across consecutive windows.',
    '结果超时': 'Result Timeout', '异常分数：': 'Anomaly Score: ',
    '模型：已建立（MCU）': 'Model: Trained (MCU)', '模型：未建立': 'Model: Not Trained',
    '模型：未知（无最新结果）': 'Model: Unknown (No Recent Result)',
    '已连接，等待采样数据': 'Connected; waiting for samples', '接收中': 'Receiving',
    '连接已结束，请断开后重连': 'Connection ended; disconnect and reconnect',
    # Rate handling
    '正在查询 MCU 实际采样率及支持档位…': 'Querying the actual MCU ODR and supported rates…',
    '已请求 ': 'Requested ', ' Hz，等待 MCU 确认；原学习模型需重新学习': ' Hz; waiting for MCU confirmation. The existing model must be retrained.',
    'MCU 当前 ': 'Current MCU ODR: ', ' Hz；切换成功后需重新学习。': ' Hz; retraining is required after a successful change.',
    '确认速率不匹配：请求 ': 'ODR mismatch: requested ', ' Hz，设备返回 ': ' Hz, but the device reported ',
    ' Hz；请重新查询。': ' Hz. Please query again.',
    '已确认切换为 ': 'ODR change confirmed: ', ' Hz；连续数据缓存已清空，请重新学习。': ' Hz. The continuous-data buffer was cleared; please retrain.',
    'MCU 采样率操作失败：': 'MCU ODR operation failed: ',
    '切换未收到确认，实际速率未知；请重新查询，界面未假定切换成功。': 'No confirmation was received for the ODR change. The actual rate is unknown; query again. The UI does not assume the change succeeded.',
    '未收到采样率能力回复：当前固件可能尚不支持 RATE 指令。原有采集可继续。': 'No ODR capability response received. The current firmware may not support the RATE command. Existing acquisition can continue.',
    # Telemetry / FFT / NVM
    'MCU 运行状态：上报超时': 'MCU Runtime: Telemetry Timeout',
    'MCU 忙碌≈': 'MCU Busy ≈', 'FFT调度 ': ' | FFT Scheduling ', 'LCD ': ' | LCD ',
    '，最长 ': ', max ', ' FPS  |  TX队列 ': ' FPS | TX Queue ', '，峰值 ': ', peak ',
    '点/s': ' samples/s', '溢出 ': ' overrun ', '读取错误 ': ' read errors ',
    'TX丢弃 ': ' TX drops ', '上传丢帧 ': ' stream drops ',
    'MCU FFT：结果超时': 'MCU FFT: Result Timeout', 'MCU FFT：等待设备结果': 'MCU FFT: Waiting for Device Result',
    'MCU FFT：等待完整连续数据窗口': 'MCU FFT: Waiting for a Complete Continuous Data Window',
    '以下频谱由 PC 计算；暂无有效 MCU FFT 结果。': 'The spectrum below is calculated by the PC; no valid MCU FFT result is currently available.',
    '已完成 ': 'Completed ', ' 组 · 跳过 ': ' windows · skipped ', ' 个分析窗口': ' analysis windows',
    ' · H743未上报结果年龄/调度时长；幅值为峰值，非RMS。': ' · H743 does not report result age or scheduling time; amplitude is peak, not RMS.',
    ' · 发布后样本时间 ': ' · Sample age after publication: ', ' ms · 调度批次最大 ': ' ms · Maximum scheduling batch: ',
    ' ms；幅值为峰值，非 RMS。': ' ms; amplitude is peak, not RMS.',
    ' 【结果超过1秒未更新】': ' [Result not updated for over 1 s]',
    '模型存储：状态超时': 'Model Storage: Status Timeout',
    '模型存储：等待 MCU 状态': 'Model Storage: Waiting for MCU Status',
    'H743模型保存：返回 ': 'H743 Model Save: return ', ' · 采集重启 ': ' · acquisition restart ',
    ' · 模型位图 ': ' · model bitmap ', '（0表示该步成功）': ' (0 = step succeeded)',
    '存在有效记录 / 最近操作成功': 'Valid record exists / latest operation succeeded',
    '无有效保存记录': 'No valid saved record', '返回错误 ': 'Error code ',
    'H743模型存储：': 'H743 Model Storage: ', '；此报文未提供启动恢复次数或Flash序号。': '; this message does not include boot-recovery count or Flash sequence number.',
    '模型存储：初始化失败 ': 'Model Storage: Initialization failed ',
    '本次启动已从 Flash 恢复模型': 'Model restored from Flash during this boot',
    '本次启动未恢复模型': 'No model restored during this boot', '启动加载失败 ': 'Boot load failed ',
    '本次启动已成功保存 ': 'Successfully saved during this boot: ', ' 次': ' times',
    '本次启动尚无成功保存': 'No successful save during this boot',
    '；最近保存错误 ': '; latest save error ', '模型存储：': 'Model Storage: ',
    '；Flash 序号 ': '; Flash sequence ',
    # Data / plots / dialogs
    'FFT 等待连续数据 ': 'FFT waiting for continuous data ', 'PC 主峰: ': 'PC Peak: ',
    'USB接收：独立进程，原始字节队列最多约64 MiB': 'USB receive: dedicated process; raw-byte queue capacity approx. 64 MiB',
    '连续性日志：': 'Continuity log: ', '已打开串口：': 'Serial port opened: ',
    '，配置波特率 ': ', baud rate ', ' bps': ' bps',
    'CSV 保存中': 'CSV recording', 'CSV 已关闭': 'CSV closed',
    '原始断点快照：': 'Raw gap snapshot: ', '错误: ': 'Error: ', '连接已关闭': 'Connection closed',
    'CONTINUITY ': 'CONTINUITY ', '等待串口线程退出': 'Waiting for serial worker to exit',
    '请先结束 CSV 保存、采样率切换或正常状态学习。': 'Stop CSV recording, ODR changes, or normal-state learning first.',
    '请先选择串口。': 'Please select a serial port first.',
    '请选择MCU原生USB对应的USB串行设备，不是CH343或STLink。': 'Select the USB serial device corresponding to the MCU native USB interface, not CH343 or STLink.',
    '原生USB CDC': 'Native USB CDC', '串口': 'Serial Port', '六位置校准': 'Six-Position Calibration',
    '保存完整原始采样': 'Save Complete Raw Samples', 'CSV (*.csv)': 'CSV (*.csv)',
    'USB CDC': 'USB CDC', '样本 ': 'Samples ', 'CRC/格式错误 ': 'CRC/format errors ',
    '接收断点 ': 'Receive gaps ', '显示断点 ': 'Display gaps ', '显示队列丢帧 ': 'Display queue drops ',
    '序号': 'sequence', '索引': 'index', '标志': 'flags', '速率': 'rate', '点': ' samples',
    # Calibration dialog
    '六位置校准 · MCU 参数保存': 'Six-Position Calibration · Save Parameters to MCU',
    '停机后操作：依次让 X+、X−、Y+、Y−、Z+、Z− 朝上。每面放稳后采集 5 秒，收到完成结果再换面。\n校准由 MCU 计算和应用；本软件不会对收到的数据重复校正。': 'Perform this procedure with the machine stopped: orient X+, X−, Y+, Y−, Z+, and Z− upward in sequence. Stabilize each face and acquire for 5 s; move to the next face only after completion is reported.\nCalibration is calculated and applied by the MCU; this software does not apply a second correction to received data.',
    '未校准三轴读数 · 约0.5秒均值': 'Uncalibrated 3-Axis Readings · Approx. 0.5 s Mean',
    '等待实时数据': 'Waiting for live data',
    '标准差 X/Y/Z：': 'Std Dev X/Y/Z: ',
    '这些数值包含重力和零偏；校准前不要求某轴恰好为±1000 mg、其余轴为0。请按传感器轴向标识摆放。': 'These values include gravity and offset. Before calibration, an axis is not expected to be exactly ±1000 mg with the other axes at zero. Orient the board according to the sensor-axis markings.',
    '开始新校准': 'Start New Calibration', '查询设备状态': 'Query Device Status',
    '取消本次校准': 'Cancel This Calibration',
    '朝上方向': 'Upward Face', '原始 X (mg)': 'Raw X (mg)', '原始 Y (mg)': 'Raw Y (mg)', '原始 Z (mg)': 'Raw Z (mg)',
    '校正残差 X / Y / Z (mg)': 'Correction Residual X / Y / Z (mg)', '结果': 'Result',
    '待采集': 'Pending', '采集所选面（5秒）': 'Capture Selected Face (5 s)',
    '本面原始均值：—': 'Current Face Raw Mean: —',
    '计算并检查六面结果': 'Calculate and Check Six-Face Results',
    '零偏/比例：待求解；综合一致性：待核验。旁轴残差为姿态提示。': 'Offset/scale: pending solution; overall consistency: pending verification. Cross-axis residuals are posture indicators.',
    '写入设备并清除旧学习模型': 'Write to Device and Clear Old Learning Model',
    '保存后需在正常运行工况下重新学习。六面校准不替代高频振动幅值/频响校验。': 'After saving, retrain under normal operating conditions. Six-position calibration does not replace high-frequency vibration amplitude/frequency-response verification.',
    '静止（仍需保持到本面采集结束）': 'Stable (remain still until this face capture completes)',
    '检测到运动 / 振动，请放稳': 'Motion / vibration detected; stabilize the device',
    '实时数据未到达或已超时；需配套 MCU_Calibration_V1_4，且无需点击“开始采集”。': 'Live data has not arrived or has timed out. Compatible MCU_Calibration_V1_4 firmware is required; do not click Start Acquisition.',
    '采集中…': 'Capturing…', '一致性超限': 'Consistency Limit Exceeded', '姿态提示': 'Posture Warning',
    '已核验': 'Verified', '明细待返回': 'Details Pending', '已采集': 'Captured',
    '待求解核验': 'Pending Solution Check', '重采所选面': 'Recapture Selected Face',
    '采集所选面': 'Capture Selected Face', '（5秒，其余面保留）': ' (5 s; other faces are retained)',
    '本面采集 %p%': 'Current face capture %p%', '已采集 ': 'Captured ', '/6 面': '/6 faces',
    '最近一面原始均值：': 'Most Recent Face Raw Mean: ',
    '零偏 ': 'Offset ', '；比例 ': '; scale ', '当前设备参数：': 'Current device parameters: ',
    '（已校准）': ' (calibrated)', '（默认值，尚未校准）': ' (default; not calibrated)',
    '当前设备参数：等待查询': 'Current device parameters: waiting for query',
    '本次候选参数：': 'Candidate parameters: ',
    '零偏/比例：通过；综合一致性：': 'Offset/scale: passed; overall consistency: ',
    '通过': 'Passed', '未通过': 'Failed',
    '\n六面合量相对1g偏差 (mg)：': '\nSix-face vector-magnitude deviation from 1 g (mg): ',
    '\nX/Y/Z 正反面对称性偏差 (mg)：': '\nX/Y/Z positive-negative face symmetry deviation (mg): ',
    '。旁轴残差>50 mg仅为黄色姿态提示。': '. Cross-axis residuals >50 mg are yellow posture warnings only.',
    '零偏/比例及综合一致性：待完成六面求解。旁轴残差为姿态提示。': 'Offset/scale and overall consistency: waiting for the six-face solution. Cross-axis residuals are posture indicators.',
    '校准尚未结束，请先点“取消本次校准”；保存过程中请等待最终确认。': 'Calibration is not finished. Click Cancel This Calibration first; while saving, wait for final confirmation.',
    '保存后需在正常运行工况下重新学习。': 'Retrain under normal operating conditions after saving.',
    # Calibration model notes and operation feedback
    '连接设备后查询校准状态。': 'Connect the device and query its calibration status.',
    '正在核对 MCU 校准协议版本…': 'Checking MCU calibration protocol version…',
    '串口已断开；未确认的采集或保存不视为成功。重连后查询设备状态。': 'Serial port disconnected. Unconfirmed capture or save operations are not considered successful. Reconnect and query device status.',
    '校准协议': 'calibration protocol', '匹配': ' matched', '不匹配，需V1.4': ' mismatch; V1.4 required',
    '尚未收到V1.4能力确认': 'V1.4 capability confirmation not received',
    'MCU版本未确认：需烧录V1.4，确认 main.c 和 calibration.inc 均已替换并重新编译。': 'MCU version not verified: flash V1.4, ensure both main.c and calibration.inc have been replaced, then rebuild.',
    '设备拒绝求解，但六面诊断明细尚未返回；请查询设备状态并确认MCU版本。': 'The device rejected the solution, but six-face diagnostic details have not been returned. Query device status and verify the MCU version.',
    '合量核验未通过：': 'Vector-magnitude check failed: ', ' 面校正后合量偏离1g ': ' face corrected magnitude deviates from 1 g by ',
    '（允许±50 mg），请检查该面倾斜及对应正反面基准。': ' (limit ±50 mg). Check the tilt of this face and the corresponding opposite-face reference.',
    '正反面对称性未通过：': 'Positive/negative face symmetry check failed: ',
    ' 轴两面的校正中点偏差 ': ' axis corrected midpoint deviation between the two faces: ',
    '（允许50 mg）。请检查这两面及各轴零偏是否稳定。': ' (limit 50 mg). Check these two faces and verify that each axis offset is stable.',
    '六面核验未通过：最大残差在 ': 'Six-face verification failed: maximum residual is on face ',
    ' 面的 ': ', axis ', ' 轴，': ', ', '（门限50 mg）。先检查该面，并核对该轴正反面；最大残差不能唯一确定问题来源。选中一面重采会保留其余数据。': ' (limit 50 mg). Check this face and its opposite face on the same axis. The maximum residual alone cannot uniquely identify the cause. Recapturing one face retains the other data.',
    '正反面差值或参数不合格。X/Y/Z 正反面差值：': 'Opposite-face differences or parameters are out of range. X/Y/Z opposite-face differences: ',
    ' mg；各轴应约为+2000 mg，请检查是否选错方向、重复同一面或正反面颠倒。': ' mg; each axis should be about +2000 mg. Check for an incorrect orientation, duplicate face, or reversed opposite faces.',
    '六面数据尚未齐全，请补采缺失面。': 'Six-face data is incomplete. Capture the missing faces.',
    '零偏/比例及综合一致性检查通过。': 'Offset/scale and overall consistency checks passed.',
    '等待 MCU 开始校准确认…': 'Waiting for MCU confirmation to start calibration…',
    '保持静止，正在采集这一面…': 'Keep still; capturing this face…',
    '等待 MCU 计算和检查六面结果…': 'Waiting for MCU to calculate and check the six-face results…',
    '正在写入设备，等待最终结果；请勿断电。': 'Writing to device and waiting for the final result; do not power off.',
    '等待 MCU 取消确认…': 'Waiting for MCU cancellation confirmation…',
    '已重新查询设备。上次操作结果未确认，请检查参数；不要将此提示当成保存成功。': 'Device queried again. The previous operation was not confirmed. Check the parameters; do not treat this message as a successful save.',
    '已重新查询设备。上次操作结果未确认，请检查参数；不要将此提示当作保存成功。': 'Device queried again. The previous operation was not confirmed. Check the parameters; do not treat this message as a successful save.',
    '校准会话进行中，可继续采集或取消。': 'Calibration session in progress. You may continue capturing or cancel.',
    '设备支持六位置校准。先停机，将板子静止放稳。': 'The device supports six-position calibration. Stop the machine and place the board in a stable position.',
    '保存成功，已读回当前参数。请安装到正常工况，分别重新学习 2500 / 5000 / 10000 / 20000 Hz；掉电恢复需重启后另行验证。': 'Save successful; current parameters have been read back. Install under normal operating conditions and retrain at 2500 / 5000 / 10000 / 20000 Hz respectively. Verify power-loss recovery separately after reboot.',
    '保存回复与读回参数不一致，请检查设备。': 'Save response does not match the parameters read back. Check the device.',
    '零偏/比例与综合一致性检查通过，可以保存。旁轴残差超过50 mg仅提示检查姿态；写入后须重新学习。': 'Offset/scale and overall consistency checks passed; saving is allowed. Cross-axis residuals above 50 mg only indicate that posture should be checked. Retrain after writing.',
    '按六个方向逐面放稳，再点击“采集所选面”。': 'Stabilize the board in each of the six orientations, then click Capture Selected Face.',
    '采集方向回复不匹配，请查询设备状态。': 'Capture-orientation response mismatch. Query device status.',
    '本面静止检查通过，可以换下一面；方向和零偏将在六面求解时核验。': 'This face passed the stillness check. You may move to the next face; orientation and offset will be checked during the six-face solution.',
    '本面未通过：': 'This face failed: ', '采集期间有振动，请放稳重试；方向会在六面求解时检查。': 'Vibration occurred during capture. Stabilize and retry; orientation will be checked during the six-face solution.',
    '采集数据中断或超时，请重试。': 'Capture data was interrupted or timed out. Please retry.',
    '收到延迟的保存回复，请查询当前参数并检查设备。': 'A delayed save response was received. Query the current parameters and check the device.',
    'MCU 已确认保存，正在读回参数…': 'MCU confirmed the save. Reading parameters back…',
    '保存未完整确认：写入返回 ': 'Save was not fully confirmed: write returned ',
    '，传感器恢复 ': ', sensor resume ', '。请查询参数；可能已提交，需要重新学习。': '. Query the parameters; the save may have been committed, and retraining is required.',
    '已取消未保存的校准；原有参数保持。': 'Uncommitted calibration was cancelled; existing parameters are retained.',
    'MCU 拒绝操作：': 'MCU rejected the operation: ',
    '固件不支持校准命令，请使用 MCU_Calibration_V1。': 'Firmware does not support calibration commands. Use MCU_Calibration_V1.',
    'MCU报告已采集，但六面明细未完整返回。请检查当前固件版本及串口日志；缺失值不会被当成0。': 'MCU reported that capture completed, but the six-face details are incomplete. Check the firmware version and serial log; missing values are not treated as zero.',
    '未收到校准能力回复。请检查是否使用 MCU_Calibration_V1；原有采集功能仍可使用。': 'No calibration capability response received. Check whether MCU_Calibration_V1 is in use; existing acquisition functions remain available.',
    ' 未收到完整确认，结果未知；正在查询设备，请勿重复写入。': ' was not fully confirmed; the result is unknown. Querying the device; do not write again.',
    # Learning transaction feedback
    '学习指令已排队，等待串口发送。': 'Learning command queued; waiting for serial transmission.',
    '取消指令已排队，等待发送。': 'Cancel command queued; waiting to be sent.',
    '学习指令已发送（第': 'Learning command sent (attempt ', '次），等待 MCU 确认。': '); waiting for MCU confirmation.',
    '取消已发送，等待 MCU 确认。': 'Cancel command sent; waiting for MCU confirmation.',
    'MCU已确认取消学习。': 'MCU confirmed learning cancellation.',
    'MCU已接收学习指令，等待学习状态；请保持固定安装和正常工况。': 'MCU accepted the learning command; waiting for the learning state. Keep the device firmly mounted and operating normally.',
    '设备正忙（可能正在学习、保存或切换采样率）': 'Device is busy (possibly learning, saving, or changing ODR)',
    '传感器尚未就绪': 'Sensor is not ready',
    '六位置校准会话尚未结束，请先取消或保存校准': 'Six-position calibration session is still active. Cancel or save calibration first',
    '正在保存模型，请稍后再试': 'Model is being saved. Please try again later',
    '正在切换采样率，请稍后再试': 'ODR is being changed. Please try again later',
    'MCU拒绝操作：': 'MCU rejected the operation: ', '。本次不视为学习成功。': '. This attempt is not considered successful.',
    'MCU已进入正常状态学习，约1秒预热＋30秒有效数据。': 'MCU entered normal-state learning: approx. 1 s warm-up plus 30 s of valid data.',
    'MCU已退出学习状态。': 'MCU exited the learning state.',
    '串口已断开，操作结果未确认。': 'Serial port disconnected; operation result was not confirmed.',
    '尚未收到 MCU 确认，正在有限重试。': 'No MCU confirmation received; retrying with a limited number of attempts.',
    'MCU已接收指令，但未确认持续学习状态；请检查采集错误或复位日志。': 'MCU accepted the command but did not confirm a sustained learning state. Check acquisition errors or reset logs.',
    '操作未收到完整确认，已停止重试，请查看串口日志。': 'The operation did not receive full confirmation. Retries stopped; check the serial log.',
    # Additional complete messages and calibration-orientation fragments
    '串口指令未完整写出': 'Serial command was not fully transmitted',
    '当前H743固件未提供旧校准对话框所需的完整确认协议。': 'The current H743 firmware does not provide the complete confirmation protocol required by the legacy calibration dialog.',
    '当前H743固件缺少旧版校准对话框需要的完整确认报文；暂不开放写入操作。': 'The current H743 firmware lacks the complete confirmation messages required by the legacy calibration dialog; write operations remain disabled.',
    '退出前请先取消校准；保存过程中请等待最终确认。': 'Cancel calibration before exiting. During saving, wait for final confirmation.',
    ' 轴正方向朝上': ' axis positive direction facing up',
    ' 轴负方向朝上': ' axis negative direction facing up',
    ' 对应传感器 ': ' corresponds to sensor ',
    'MCU 启动标识 V': 'MCU boot identifier V',
    '；尚未收到V1.4能力确认': '; V1.4 capability confirmation has not been received',
    '已重新查询设备。上次操作结果未确认，请检查参数；不要将此提示当成保存成功。': 'Device queried again. The previous operation was not confirmed. Check the parameters; do not treat this message as a successful save.',
    ' [设备返回 ': ' [device returned ',
    'MCU已接收学习指令': 'MCU accepted the learning command',
    'MCU已取消学习': 'MCU cancelled learning',
}

# Ignore short/punctuation-only English fragments in the reverse map: they are
# too ambiguous for safe substring replacement (for example a comma-space).
EN_ZH = {v: k for k, v in ZH_EN.items() if len(v.strip()) >= 4 and v not in ('中文', 'English') and k != '语言 / Language'}
EN_ZH['MCU rejected the operation: '] = 'MCU 拒绝操作：'
_ZH_KEYS = tuple(sorted(ZH_EN, key=len, reverse=True))
_EN_KEYS = tuple(sorted(EN_ZH, key=len, reverse=True))


@lru_cache(maxsize=8192)
def translate_text(value, language='zh'):
    """Translate a UI string in either direction, preserving numbers and protocol tokens."""
    if value is None:
        return value
    text = str(value)
    if language == 'en':
        # Translate variable-rich status lines as templates to keep punctuation
        # and axis/queue fields readable in both languages.
        match = re.fullmatch(r'六面核验未通过：最大残差在 (.+?) 面的 ([XYZ]) 轴，([+-]?[0-9]+(?:\.[0-9]+)?) mg（门限50 mg）。先检查该面，并核对该轴正反面；最大残差不能唯一确定问题来源。选中一面重采会保留其余数据。', text)
        if match:
            face, axis, amount = match.groups()
            return (f'Six-face verification failed: maximum residual is on face {face}, axis {axis}, '
                    f'{amount} mg (limit 50 mg). Check this face and its opposite face on the same axis. '
                    'The maximum residual alone cannot uniquely identify the cause. Recapturing one face retains the other data.')
        match = re.fullmatch(r'MCU 忙碌≈([0-9.]+)%  \|  FFT调度 ([0-9.]+) ms / ([0-9.]+)s  \|  LCD ([0-9.]+) ms，最长 ([0-9.]+) ms，([0-9.]+) FPS  \|  TX队列 (\d+)/(\d+)，峰值 (\d+)', text)
        if match:
            busy, fft, period, lcd, lcd_max, fps, q, qcap, qmax = match.groups()
            return (f'MCU Busy ≈{busy}% | FFT scheduling {fft} ms / {period} s | '
                    f'LCD {lcd} ms (max {lcd_max} ms, {fps} FPS) | TX queue {q}/{qcap} (peak {qmax})')
        match = re.fullmatch(r'FIFO (\d+)点/s · level=(\d+) · 溢出 (\d+) · 读取错误 (\d+) · LCD (\d+) / (\d+)fps · TX丢弃 (\d+) · 上传丢帧 (\d+)', text)
        if match:
            rate, level, overrun, errors, lcd, fps, txdrop, streamdrop = match.groups()
            return (f'FIFO {rate} samples/s · level={level} · overruns {overrun} · read errors {errors} · '
                    f'LCD {lcd} / {fps} fps · TX drops {txdrop} · stream drops {streamdrop}')
        match = re.fullmatch(r'(接收中|已连接，等待采样数据|连接已结束，请断开后重连) \| USB CDC \(([^)]+)\) \| Fs=(\d+) Hz \| 样本 (\d+) \| CRC/格式错误 (\d+) \| 接收断点 (\d+)（序号(\d+)/索引(\d+)/标志(\d+)/速率(\d+)）\| 显示断点 (\d+) \| 显示队列丢帧 (\d+) \| CSV (\d+) 点', text)
        if match:
            state, port, fs, samples, crc, gaps, seq, idx, flags, rate_err, display_gaps, drops, csv_points = match.groups()
            state = {'接收中':'Receiving','已连接，等待采样数据':'Connected; waiting for samples','连接已结束，请断开后重连':'Connection ended; disconnect and reconnect'}[state]
            return (f'{state} | USB CDC ({port}) | Fs={fs} Hz | Samples {samples} | CRC/format errors {crc} | '
                    f'Receive gaps {gaps} (seq {seq}/index {idx}/flags {flags}/rate {rate_err}) | '
                    f'Display gaps {display_gaps} | Display queue drops {drops} | CSV {csv_points} samples')
        pairs = ZH_EN
        keys = _ZH_KEYS
    else:
        match = re.fullmatch(r'Six-face verification failed: maximum residual is on face (.+?), axis ([XYZ]), ([+-]?[0-9]+(?:\.[0-9]+)?) mg \(limit 50 mg\)\. Check this face and its opposite face on the same axis\. The maximum residual alone cannot uniquely identify the cause\. Recapturing one face retains the other data\.', text)
        if match:
            face, axis, amount = match.groups()
            return (f'六面核验未通过：最大残差在 {face} 面的 {axis} 轴，{amount} mg（门限50 mg）。'
                    '先检查该面，并核对该轴正反面；最大残差不能唯一确定问题来源。选中一面重采会保留其余数据。')
        match = re.fullmatch(r'MCU Busy ≈([0-9.]+)% \| FFT scheduling ([0-9.]+) ms / ([0-9.]+) s \| LCD ([0-9.]+) ms \(max ([0-9.]+) ms, ([0-9.]+) FPS\) \| TX queue (\d+)/(\d+) \(peak (\d+)\)', text)
        if match:
            busy, fft, period, lcd, lcd_max, fps, q, qcap, qmax = match.groups()
            return (f'MCU 忙碌≈{busy}%  |  FFT调度 {fft} ms / {period}s  |  LCD {lcd} ms，最长 {lcd_max} ms，{fps} FPS  |  TX队列 {q}/{qcap}，峰值 {qmax}')
        match = re.fullmatch(r'FIFO (\d+) samples/s · level=(\d+) · overruns (\d+) · read errors (\d+) · LCD (\d+) / (\d+) fps · TX drops (\d+) · stream drops (\d+)', text)
        if match:
            rate, level, overrun, errors, lcd, fps, txdrop, streamdrop = match.groups()
            return (f'FIFO {rate}点/s · level={level} · 溢出 {overrun} · 读取错误 {errors} · '
                    f'LCD {lcd} / {fps}fps · TX丢弃 {txdrop} · 上传丢帧 {streamdrop}')
        match = re.fullmatch(r'(Receiving|Connected; waiting for samples|Connection ended; disconnect and reconnect) \| USB CDC \(([^)]+)\) \| Fs=(\d+) Hz \| Samples (\d+) \| CRC/format errors (\d+) \| Receive gaps (\d+) \(seq (\d+)/index (\d+)/flags (\d+)/rate (\d+)\) \| Display gaps (\d+) \| Display queue drops (\d+) \| CSV (\d+) samples', text)
        if match:
            state, port, fs, samples, crc, gaps, seq, idx, flags, rate_err, display_gaps, drops, csv_points = match.groups()
            state = {'Receiving':'接收中','Connected; waiting for samples':'已连接，等待采样数据','Connection ended; disconnect and reconnect':'连接已结束，请断开后重连'}[state]
            return (f'{state} | USB CDC ({port}) | Fs={fs} Hz | 样本 {samples} | CRC/格式错误 {crc} | '
                    f'接收断点 {gaps}（序号{seq}/索引{idx}/标志{flags}/速率{rate_err}）| '
                    f'显示断点 {display_gaps} | 显示队列丢帧 {drops} | CSV {csv_points} 点')
        pairs = EN_ZH
        keys = _EN_KEYS
    if text in pairs:
        return pairs[text]
    # Longest phrases first so a specific sentence wins over generic fragments.
    for source in keys:
        if source and source in text:
            text = text.replace(source, pairs[source])
    return text


def _translate_widget_value(widget, slot, current, setter, language):
    """Translate from the immutable source value, not from the last translation.

    UI refresh callbacks may update labels while the selected language is English.
    If the visible value differs from the last rendered value, it is treated as a
    new source string (the application emits source strings in Chinese).
    """
    source_key = f"_coremaker_i18n_source_{slot}"
    rendered_key = f"_coremaker_i18n_rendered_{slot}"
    source = widget.property(source_key)
    rendered = widget.property(rendered_key)
    if source is None or current != rendered:
        source = current
    translated = translate_text(source, language)
    if translated != current:
        setter(translated)
    widget.setProperty(source_key, source)
    widget.setProperty(rendered_key, translated)


def translate_widget_tree(root, language='zh'):
    """Translate Qt widgets idempotently while allowing live labels to update."""
    from PySide6 import QtCore, QtWidgets
    widgets = [root] + root.findChildren(QtWidgets.QWidget)
    item_source_role = int(QtCore.Qt.ItemDataRole.UserRole) + 701
    item_rendered_role = item_source_role + 1
    tip_source_role = item_source_role + 2
    tip_rendered_role = item_source_role + 3

    for widget in widgets:
        # The language selector caption is intentionally bilingual and must
        # never be translated or used as a source string.
        if widget.property('_coremaker_i18n_skip'):
            continue

        try:
            tip = widget.toolTip()
            if tip:
                _translate_widget_value(widget, 'tooltip', tip, widget.setToolTip, language)
        except Exception:
            pass

        if isinstance(widget, QtWidgets.QAbstractButton):
            current = widget.text()
            _translate_widget_value(widget, 'text', current, widget.setText, language)
        elif isinstance(widget, QtWidgets.QLabel):
            current = widget.text()
            _translate_widget_value(widget, 'text', current, widget.setText, language)
        elif isinstance(widget, QtWidgets.QGroupBox):
            current = widget.title()
            _translate_widget_value(widget, 'title', current, widget.setTitle, language)
        elif isinstance(widget, QtWidgets.QComboBox):
            for index in range(widget.count()):
                current = widget.itemText(index)
                source_key = f'_coremaker_i18n_combo_source_{index}'
                rendered_key = f'_coremaker_i18n_combo_rendered_{index}'
                source = widget.property(source_key)
                rendered = widget.property(rendered_key)
                if source is None or current != rendered:
                    source = current
                translated = translate_text(source, language)
                if translated != current:
                    widget.setItemText(index, translated)
                widget.setProperty(source_key, source)
                widget.setProperty(rendered_key, translated)
        elif isinstance(widget, QtWidgets.QProgressBar):
            current = widget.format()
            _translate_widget_value(widget, 'format', current, widget.setFormat, language)
        elif isinstance(widget, QtWidgets.QTableWidget):
            for row in range(widget.rowCount()):
                for col in range(widget.columnCount()):
                    item = widget.item(row, col)
                    if item is None:
                        continue
                    current = item.text()
                    source = item.data(item_source_role)
                    rendered = item.data(item_rendered_role)
                    if source is None or current != rendered:
                        source = current
                    translated = translate_text(source, language)
                    if translated != current:
                        item.setText(translated)
                    item.setData(item_source_role, source)
                    item.setData(item_rendered_role, translated)
                    tip = item.toolTip()
                    if tip:
                        tip_source = item.data(tip_source_role)
                        tip_rendered = item.data(tip_rendered_role)
                        if tip_source is None or tip != tip_rendered:
                            tip_source = tip
                        translated_tip = translate_text(tip_source, language)
                        if translated_tip != tip:
                            item.setToolTip(translated_tip)
                        item.setData(tip_source_role, tip_source)
                        item.setData(tip_rendered_role, translated_tip)

