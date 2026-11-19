# STM32H743ZIT6 + IIS3DWB10IS 三轴振动监测与边缘分析平台
**COREMAKER | 3-Axis Vibration Monitoring & Edge Analytics**

基于 **STM32H743ZIT6** 与 **ST IIS3DWB10IS** 的三轴振动采集与边缘分析项目。MCU 端完成传感器 FIFO 采集、实时特征计算、FFT 分析、正常状态学习和异常状态判断；配套 Windows PC 上位机通过原生 USB FS CDC 实现设备控制、波形/频谱显示、数据连续性监控及 CSV 导出。

> 本仓库包含 STM32CubeIDE 固件工程和中英文双语 PC 上位机。当前固件支持最高 **80 kS/s** 采样率。
<img width="2480" height="1275" alt="image" src="https://github.com/user-attachments/assets/4d22433f-499f-4898-93a2-d6e7e77746da" />
<img width="1600" height="1164" alt="image" src="https://github.com/user-attachments/assets/7bea6ff4-7a6d-4fdf-a241-f83b356783be" />

## 项目维护者与联系方式 \| Project Maintainer & Contact

- **Name / 姓名**: Billy
- **交流群 / Discussion Group**: 925643491
- **Email / 邮箱**: <a845656974@outlook.com>
- **Phone / 电话**: +86 15622736378

------------------------------------------------------------------------
---

## 目录

- [项目功能](#项目功能)
- [硬件组成](#硬件组成)
- [系统架构](#系统架构)
- [采样率与数据处理](#采样率与数据处理)
- [PC 上位机使用](#pc-上位机使用)
- [STM32 固件编译](#stm32-固件编译)
- [串口命令](#串口命令)
- [关键注意事项](#关键注意事项)
- [工程目录](#工程目录)
- [验证脚本](#验证脚本)
- [License](#license)

---

## 项目功能

### MCU 固件

- IIS3DWB10IS 三轴加速度数据采集。
- SPI1 + DMA 读取传感器 FIFO，INT1 用于 FIFO 水位/溢出事件通知。
- 传感器量程配置为 **±50 g**。
- 支持 2.5 kHz、5 kHz、10 kHz、20 kHz、40 kHz、80 kHz 六档采样率。
- 三轴振动数据实时处理：5 Hz 高通、约 200 ms 特征窗口。
- 每轴计算 RMS、峰峰值（P-P）和峰值因子（Crest Factor），共 9 项特征。
- MCU 端 1024 点 Hann 窗 FFT，输出 X/Y/Z 轴主峰频率与峰值幅度。
- 基于正常工况样本建立统计基线，并在 MCU 本地执行异常评分与状态判断。
- ST7796 LCD 实时显示三轴振动状态与波形信息。
- 原生 USB FS CDC 与 PC 上位机通信。
- 支持低采样率模型 Flash 保存及高采样率 RAM 模型管理。

### Windows PC 上位机

- 中文 / English 双语界面，语言选择会保存。
- COM 端口刷新、连接、断开及采集启停。
- 查询和切换 MCU 采样率。
- 启动正常状态学习并查看学习进度、模型状态和异常分数。
- 实时显示 X/Y/Z 三轴波形。
- PC 端独立 FFT 分析，支持 1024 / 2048 / 4096 / 8192 点。
- 显示 MCU FFT 结果及设备运行遥测信息。
- CSV 原始数据记录。
- USB 数据连续性、CRC/格式错误和接收断点监控。
- 自动生成连续性诊断日志，便于问题定位。

---

## 硬件组成

| 模块 | 器件 / 接口 | 说明 |
|---|---|---|
| MCU | STM32H743ZIT6 | 主控制器 |
| 三轴加速度传感器 | ST IIS3DWB10IS | ±50 g 配置，SPI 接口 |
| LCD | ST7796 | 480 × 320，SPI 接口 |
| 传感器通信 | SPI1 | 传感器寄存器及 FIFO 读取 |
| LCD 通信 | SPI2 | LCD 显示数据传输 |
| PC 通信 | USB FS CDC | 原生 USB 虚拟串口 |

### 当前工程引脚

| 功能 | MCU 引脚 |
|---|---|
| Sensor SPI1 SCK / MISO / MOSI | PA5 / PA6 / PA7 |
| Sensor CS | PB0 |
| Sensor INT1 / INT2 | PB1 / PB2 |
| LCD SPI2 MOSI / SCK | PC3 / PB10 |
| LCD CS / DC / RESET / BL | PC1 / PC2 / PC4 / PC5 |

> 引脚信息来自当前工程配置。实际 PCB 连接请以对应硬件原理图和板卡版本为准。

---

## 系统架构

```text
IIS3DWB10IS
     │
     │ SPI1 + DMA / FIFO + INT1
     ▼
STM32H743ZIT6
     ├── 三轴原始数据采集
     ├── 振动特征计算（RMS / P-P / Crest Factor）
     ├── MCU FFT（1024-point Hann window）
     ├── 正常状态学习与异常判断
     ├── ST7796 LCD 实时显示
     └── USB FS CDC 数据与命令
                │
                ▼
         Windows PC Monitor
             ├── 实时波形
             ├── PC FFT
             ├── MCU 状态与异常分数
             ├── 数据连续性监控
             └── CSV / Diagnostics
```

MCU 是实时采集和异常判断的执行端；PC 主要负责可视化、控制、记录和辅助分析。PC 端 FFT 与 MCU 端 FFT 独立计算，使用的点数和数据窗口可能不同，因此频谱主峰结果允许存在小幅差异。

---

## 采样率与数据处理

### 支持的传感器采样率

| ODR | 说明 |
|---:|---|
| 2,500 Hz | 2.5 kS/s |
| 5,000 Hz | 5 kS/s |
| 10,000 Hz | 10 kS/s |
| 20,000 Hz | 20 kS/s |
| 40,000 Hz | 40 kS/s |
| 80,000 Hz | 80 kS/s，当前工程最高档位 |

### 正常状态学习与异常判断

1. 先将传感器/设备稳定安装在被测对象上，并确认设备处于可代表正常状态的工况。
2. 选择最终工作采样率后，再启动正常状态学习。
3. MCU 使用约 200 ms 的特征窗口，采集 **150 个有效特征块** 建立正常基线（约 30 秒有效学习数据，另有启动预热）。
4. 每个特征块包含 X/Y/Z 三轴的 RMS、P-P 和 Crest Factor，共 9 项特征。
5. 监测时，MCU 计算当前特征相对正常基线的偏离分数。当前固件以连续窗口确认异常和恢复状态。

**异常分数是相对正常基线的偏离指标，不是故障概率，也不能单独作为设备故障诊断结论。** 实际应用应结合原始波形、频谱、工况及现场检查综合判断。

### 模型存储说明

| 采样率 | 模型保存方式 |
|---|---|
| 2.5 / 5 / 10 / 20 kS/s | 支持保存到 MCU Flash |
| 40 / 80 kS/s | 当前固件为 RAM_ONLY，不写入 Flash |

在 40 kS/s 或 80 kS/s 下，设备断电或复位后 RAM 模型会丢失，需要重新执行正常状态学习。切换采样率后也应重新学习，不能直接沿用其他采样率下的模型。

---

## PC 上位机使用

### 环境要求

- Windows 10 / 11
- 64-bit Python 3.12 或更新版本（启动脚本当前检测 Python 3.12、3.13、3.14）
- USB 数据线及设备原生 USB FS CDC 接口

PC 依赖位于 `PC/requirements.txt`：

- PySide6
- pyqtgraph
- numpy
- pyserial

### 启动步骤

1. 下载或克隆本仓库，并完整保留目录结构。
2. 进入 `PC/` 文件夹。
3. 双击 `start.bat`（或 `Start_Windows.bat`）。
4. 首次启动时，脚本会创建独立虚拟环境 `.venv_h743_ui` 并安装所需 Python 依赖。
5. 软件启动后选择 `中文` 或 `English`。
6. 点击刷新串口，选择 MCU 原生 USB CDC 对应的 COM 端口。
7. 保持默认波特率 115200，点击连接。
8. 查询当前采样率，按需选择采样率并应用。
9. 启动采集或正常状态学习；需要保存数据时点击 `Save CSV / 保存 CSV`。

> 本设备使用原生 USB FS CDC。PC 界面的波特率选项用于串口接口配置，通常保持默认 115200 即可；不要误选 CH343 或 ST-Link 虚拟串口。

### CSV 数据字段

| 字段 | 含义 |
|---|---|
| `seq` | 数据包序号 |
| `sample_index` | 样本索引 |
| `fs_Hz` | 采样率（Hz） |
| `flags` | 数据包标志 |
| `raw_x / raw_y / raw_z` | 三轴原始传感器数据 |
| `x_mg / y_mg / z_mg` | 换算后的三轴加速度（mg） |

PC 连接期间会在 `PC/diagnostics/` 生成连续性诊断 JSONL 日志。发生异常时，建议同时保留 CSV、诊断日志和界面截图。

---

## STM32 固件编译

本仓库提供 STM32CubeIDE 工程。

1. 安装 STM32CubeIDE 及其配套 ARM GNU 工具链。
2. 打开 STM32CubeIDE。
3. 选择 `File → Import → Existing Projects into Workspace`。
4. 选择仓库中的 `STM32H743ZI_IIS3DWB10IS/` 工程目录。
5. 导入后选择 `Debug` 配置并执行 `Build Project`。
6. 通过 ST-Link 或对应调试下载接口烧录到 STM32H743ZIT6 硬件。

工程主要目录包括 `Core/`、`Drivers/`、`Middlewares/` 和 `USB_DEVICE/`。首次导入后如遇到工具链路径或 CubeIDE 版本差异，请检查工程的 MCU、编译器和链接脚本设置。

> 本 README 描述工程结构和推荐编译流程；不同电脑上的首次导入、工具链配置及实际硬件下载仍需在本地环境完成验证。

---

## 串口命令

PC 上位机通常会自动发送状态和采样率查询。开发调试时，也可通过 USB CDC 发送以下文本命令（命令以换行结束）：

| 命令 | 功能 |
|---|---|
| `STATUS` / `INFO` | 查询设备初始化、LCD、采样率及存储状态 |
| `START` | 开始向 PC 上传采样数据 |
| `STOP` | 停止向 PC 上传采样数据 |
| `RATE?` | 查询当前采样率及支持档位 |
| `RATE 10000` | 设置采样率，例如 10000 Hz |
| `LEARN` | 启动 MCU 正常状态学习 |
| `SAVE` | 请求保存当前模型/配置 |
| `CLEAR` | 清除当前学习模型 |
| `KEY UP` / `KEY DOWN` / `KEY OK` / `KEY BACK` | 模拟 LCD 按键操作 |

`RATE` 支持值：`2500`、`5000`、`10000`、`20000`、`40000`、`80000`。

---

## 关键注意事项

- **先固定安装，再学习。** 学习过程中不要移动设备、改变安装方向或改变被测设备工况。
- **先确定采样率，再学习。** 修改采样率后需要重新学习正常基线。
- **40K / 80K 模型不写入 Flash。** 断电或复位后必须重新学习。
- **当前 PC 版本未开放 H743 六位置校准对话框。** 固件包含相关底层命令，但当前配套上位机版本不会开放该校准 GUI 流程；不要将其视为已经完成的 PC 校准功能。
- **当前 H743 固件未实现 PC 端学习取消流程。** 请在启动学习前确认工况稳定，并等待学习完成。
- 如果发生 FIFO overrun、USB 接收断点或 CRC/格式错误，请保存诊断日志和原始 CSV，并降低采样率进行对照测试。
- 本项目用于振动采集与状态监测开发验证；异常评分不替代专业设备诊断和安全保护系统。

---

## 工程目录

```text
.
├── PC/
│   ├── app.py
│   ├── i18n.py
│   ├── protocol.py
│   ├── detection.py
│   ├── telemetry.py
│   ├── continuity.py
│   ├── raw_transport.py
│   ├── requirements.txt
│   ├── start.bat
│   ├── Start_Windows.bat
│   └── test_*.py
│
└── STM32H743ZI_IIS3DWB10IS/
    ├── Core/
    │   ├── Inc/
    │   └── Src/
    ├── Drivers/
    ├── Middlewares/
    ├── USB_DEVICE/
    ├── .project
    └── .cproject
```

---

## 验证脚本

`PC/` 目录包含若干开发验证脚本，例如：

- `test_10k.py`
- `test_20k.py`
- `test_high_rate.py`
- `test_h743_usb.py`
- `test_continuity.py`
- `test_firmware_link.py`
- `test_i18n.py`

这些脚本用于配套设备、固件和 PC 上位机的开发调试。运行硬件相关测试前，请先连接对应设备，并确认串口端口、采样率和固件版本正确。

---

## License

当前仓库未提供独立的项目级 `LICENSE` 文件。仓库中 STM32 HAL、CMSIS 和 USB Middleware 等第三方组件保留各自原有许可文件。若计划复制、修改或用于商业项目，请先核实各组件许可，并为本项目补充明确的项目级 License。

---

# English

## Overview

A 3-axis vibration acquisition and edge analytics platform based on **STM32H743ZIT6** and **ST IIS3DWB10IS**.

The MCU handles sensor FIFO acquisition, vibration feature extraction, FFT analysis, normal-state learning and anomaly-state evaluation. A bilingual Windows PC application communicates with the board through native USB FS CDC for device control, waveform/spectrum visualization, continuity monitoring and CSV recording.

### Key Features

- IIS3DWB10IS 3-axis acceleration acquisition, configured for ±50 g.
- SPI1 + DMA sensor communication with FIFO and INT1 event handling.
- Selectable ODR: 2.5 / 5 / 10 / 20 / 40 / 80 kHz.
- 5 Hz high-pass filtering and approximately 200 ms feature windows.
- RMS, peak-to-peak and crest-factor features for each axis.
- 1024-point Hann-window FFT on the MCU.
- On-device normal baseline learning and anomaly scoring.
- ST7796 480 × 320 SPI display.
- Native USB FS CDC communication.
- Chinese / English Windows PC application.
- PC waveform plots, configurable FFT, CSV recording and continuity diagnostics.

### PC Quick Start

1. Install 64-bit Python 3.12 or later (the launcher checks Python 3.12–3.14).
2. Open the `PC/` directory.
3. Run `start.bat`.
4. The launcher creates `.venv_h743_ui` and installs dependencies from `requirements.txt`.
5. Select Chinese or English, refresh COM ports and connect to the board's native USB CDC port.
6. Query the ODR, select the required rate, and apply it.
7. Start acquisition or normal-state learning. Use **Save CSV** to record data.

### Important Notes

- 40 kS/s and 80 kS/s learned models are RAM-only and must be relearned after reset or power loss.
- Relearn the normal baseline after changing the sampling rate.
- The anomaly score is a deviation metric, not a failure probability.
- The current PC release does not expose the H743 six-position calibration GUI.
- The current H743 firmware does not provide the PC learning-cancel workflow.

**COREMAKER — Shenzhen Xintu Chuangke Electronic Technology Co., Ltd.**
