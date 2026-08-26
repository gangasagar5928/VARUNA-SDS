# VARUNA-SDS
> **"Adaptive Subsea Acoustic Waveform Synthesis for Autonomous Underwater Vehicles"**  
> *Named after Varuna, the ancient Vedic deity of the Oceans and Celestial Waters + Software-Defined Sonar.*

**Sponsoring Organization:** Ministry of Earth Sciences (MoES)  
**Theme:** Hardware | Robotics & Drones / Oceanography  

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
- **Comprehensive Acoustic Simulation**: Ocean sound speed (Mackenzie), Thorp absorption, thermocline propagation, and matched-filter receiver analysis.
- **Low-Cost Prototype BOM**: Complete working transmitter prototype under **₹935 INR** (~$5.80 USD production target).

---

## 📂 Project Structure

```
VARUNA-SDS/
├── README.md                  # Project overview & branding
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
