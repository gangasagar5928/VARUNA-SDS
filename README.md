# VARUNA-SDS
> **"Adaptive Subsea Acoustic Waveform Synthesis for Autonomous Underwater Vehicles"**  
> *Named after Varuna, the ancient Vedic deity of the Oceans and Celestial Waters + Software-Defined Sonar.*

[![VARUNA-SDS CI Pipeline](https://github.com/gangasagar5928/VARUNA-SDS/actions/workflows/ci.yml/badge.svg)](https://github.com/gangasagar5928/VARUNA-SDS/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Sponsoring Organization:** Ministry of Earth Sciences (MoES)  
**Theme:** Hardware | Robotics & Drones / Oceanography  

---

## 🌊 System Architecture & Visual Design

![VARUNA-SDS Hardware Layer Architecture](assets/varuna_sds_exploded_view.jpg)

![VARUNA-SDS Onboard AUV Integration](assets/varuna_sds_auv_integration.jpg)

---

## 🌊 Overview

Conventional active sonars rely on fixed-frequency hardware oscillators that degrade in underwater thermoclines, temperature stratification, and multipath acoustic fading. **VARUNA-SDS** applies Software-Defined Radio (SDR) principles to underwater acoustics, utilizing Direct Digital Synthesis (DDS) via DMA to dynamically synthesize complex acoustic waveforms (CW Pings, Linear Frequency Modulation [LFM] Chirps) in real time while driving piezoceramic transducers via a high-efficiency Class-D amplifier.

---

## 🚀 Key Features

- **Direct Digital Synthesis (DDS) Engine**: Real-time fixed-point waveform synthesis at 500 kSPS.
  - **Mode A (Monofrequency CW Ping)**: 40 kHz pulse.
  - **Mode B (LFM Chirp)**: 35 kHz -> 45 kHz linear frequency sweep (pulse compression gain \(\approx +17\text{ dB}\)).
- **Dynamic Run-Time Reconfiguration**: Non-blocking UART protocol for live updates to frequency, bandwidth, pulse width, and pulse repetition interval (PRI).
- **High-Efficiency Class-D Power Stage**: Driven via PAM8302 (>85% efficiency) with a tuned 2nd-order LC reconstruction filter (\(>33\text{ dB}\) PWM carrier suppression).
- **Subsea Modular Hardware Architecture**:
  1. **Layer 1**: Subsea Pressure Hull Layer (IP68 Anodized Aluminum 6061 Vessel Base).
  2. **Layer 2**: Power Regulation & Isolation Layer (DC-DC Buck Converter + 24V AUV Bus Isolation + TP4056 USB-C Rail).
  3. **Layer 3**: AUV Command & Telemetry Layer (UART/RS485 Transceiver, SPI Telemetry Headers, Status LEDs).
  4. **Layer 4**: Direct Digital Synthesis (DDS) Core Layer (STM32F103/ESP32, Internal High-Speed DAC, DMA Controller).
  5. **Layer 5**: Reconstruction & Power Amplifier Layer (PAM8302 Class-D Audio Power Module + 100uH/100nF LC Filter + Impedance Matching Transformer).
  6. **Layer 6**: Acoustic Transducer & Aperture Layer (40kHz Waterproof Piezoceramic Projector Disc + Watertight O-ring Seal + IP68 Subsea Cable Gland).
- **Comprehensive Acoustic Simulation**: Ocean sound speed (Mackenzie), Thorp absorption, thermocline propagation, and matched-filter receiver analysis.
- **Physical Specifications**: Cylindrical Payload (120 mm Height x 55 mm Diameter, Volume \(\approx 362\text{ cm}^3\), Weight \(\approx 620\text{ g}\) in air).

---

## 📂 Project Structure

```
VARUNA-SDS/
├── README.md                  # Project overview & visual architecture
├── assets/                    # High-resolution CAD exploded views & AUV renders
│   ├── varuna_sds_exploded_view.jpg
│   └── varuna_sds_auv_integration.jpg
├── docs/
│   ├── PRD.md                 # Product Requirements Document
│   ├── schematic_guide.md     # Wiring, PAM8302 & LC filter schematics, piezo desoldering
│   └── state_machine.md       # Execution state machine & timing constraints
├── firmware/
│   ├── platformio.ini         # ESP32 and STM32 build configuration
│   ├── include/
│   │   ├── config.h           # System pinouts & default parameters
│   │   ├── dds_engine.h       # DDS LUT & LFM chirp synthesis API
│   │   ├── sonar_protocol.h   # UART command parser API
│   │   └── hal_dac.h          # Hardware Abstraction Layer for DAC/DMA & Amp
│   └── src/
│       ├── dds_engine.c       # Fixed-point DDS synthesis & windowing
│       ├── sonar_protocol.c   # Command line parser & configuration handler
│       ├── hal_esp32_dac.c    # ESP32 DAC/DMA & PAM8302 control
│       └── main.cpp           # System state machine & main loop
├── simulation/
│   ├── dds_synthesizer.py     # Python DDS waveform generator
│   ├── acoustic_channel.py    # Ocean channel model (Mackenzie, Thorp, Multipath)
│   ├── matched_filter.py      # Matched filter receiver & pulse compression
│   ├── lc_filter_sim.py       # PAM8302 LC filter model & Bode plot analysis
│   └── run_demo.py            # End-to-end simulation benchmark runner
└── tests/
    └── test_dds.py            # Automated unit test suite
```

---

## 🛠️ Quick Start

### 1. Run Python Simulation & Benchmarks
```powershell
python simulation/run_demo.py
```

### 2. Run Automated Verification Tests
```powershell
python tests/test_dds.py
```

### 3. Build & Flash Firmware (ESP32)
```powershell
pio run -e esp32dev -t upload
```

---

## 📊 Performance Benchmark

| Metric | Mode A (CW 40 kHz) | Mode B (LFM Chirp 35–45 kHz) |
| :--- | :--- | :--- |
| **Acoustic Bandwidth** | ~200 Hz | 10,000 Hz |
| **Pulse Duration** | 5.0 ms | 5.0 ms |
| **Time-Bandwidth Product** | 1.0 | 50.0 |
| **Matched Filter Gain** | 0.00 dB | **+16.99 dB** |
| **Range Resolution (\(\Delta R\))** | 380.4 cm | **7.6 cm (50x finer)** |
| **LC Carrier Suppression** | > 33 dB @ 250 kHz | > 33 dB @ 250 kHz |
| **Source Level (SL)** | 183 dB re 1µPa @ 1m | 183 dB re 1µPa @ 1m |
| **Operating Depth** | 100 m (IP68 Rated) | 100 m (IP68 Rated) |
