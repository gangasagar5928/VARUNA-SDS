# VARUNA-SDS — Complete Builder's Wiki

> **"Adaptive Subsea Acoustic Waveform Synthesis for Autonomous Underwater Vehicles"**
>
> This is the full beginner-to-advanced guide for building, understanding, and running VARUNA-SDS.
> No prior electronics or signal processing knowledge assumed.

---

## Table of Contents

1. [What is Sonar — and why does it matter?](#1-what-is-sonar--and-why-does-it-matter)
2. [Why existing sonars fail underwater](#2-why-existing-sonars-fail-underwater)
3. [What makes VARUNA-SDS different](#3-what-makes-varuna-sds-different)
4. [Core concepts explained simply](#4-core-concepts-explained-simply)
5. [Hardware you need to buy](#5-hardware-you-need-to-buy)
6. [Tools you need](#6-tools-you-need)
7. [Step-by-step hardware assembly](#7-step-by-step-hardware-assembly)
8. [Software setup on your computer](#8-software-setup-on-your-computer)
9. [Flashing firmware to ESP32](#9-flashing-firmware-to-esp32)
10. [Running the Python simulation](#10-running-the-python-simulation)
11. [Testing and verifying the build](#11-testing-and-verifying-the-build)
12. [Controlling VARUNA-SDS over serial](#12-controlling-varuna-sds-over-serial)
13. [Water tank test procedure](#13-water-tank-test-procedure)
14. [Troubleshooting guide](#14-troubleshooting-guide)
15. [Understanding the acoustic numbers](#15-understanding-the-acoustic-numbers)
16. [Scaling to production](#16-scaling-to-production)
17. [Glossary of terms](#17-glossary-of-terms)

---

## 1. What is Sonar — and why does it matter?

**Sonar** stands for **So**und **Na**vigation **a**nd **R**anging. It is the same principle bats use to avoid obstacles — you emit a sound pulse, it bounces off something, and you measure how long the echo takes to come back.

```
Sound pulse OUT  →  [Water]  →  hits object
Echo pulse BACK  ←  [Water]  ←  reflects back

Distance = (Time of Return × Speed of Sound) ÷ 2
```

Sonar is used because **light doesn't travel well underwater** — water absorbs it within a few metres. Sound, on the other hand, travels ~1500 m/s in seawater and can reach hundreds of metres. This makes it the primary sensing technology for:

- Autonomous Underwater Vehicles (AUVs) navigating the seafloor.
- Fish-finder systems used by fishing boats.
- Scientific ocean mapping (bathymetry).
- Navy submarines detecting other vessels.
- Port security systems.

---

## 2. Why existing sonars fail underwater

### Problem 1: Thermoclines

The ocean is not uniform — temperature drops with depth. When sound crosses a boundary from warm water to cold water (called a **thermocline**), it bends or reflects instead of travelling straight. This kills the echo return from a fixed-frequency sonar.

```
Surface (warm, 28°C)  → sound goes straight
—————————————————————  ← THERMOCLINE (sudden temp drop)
Deep water (cold, 10°C) → sound bends sideways
                                       [target never reached]
```

### Problem 2: Multipath Interference

Sound also reflects off the sea surface and the seafloor simultaneously, creating multiple copies of the echo that arrive at slightly different times. This **smears** the echo and makes it impossible to tell one target from two targets.

### Problem 3: Fixed Hardware Oscillators

Traditional sonars use a crystal oscillator — a small piece of quartz that vibrates at exactly one frequency (e.g., 40 kHz). You **cannot change the frequency** without replacing the hardware. If the ocean conditions demand a different frequency, you are stuck.

---

## 3. What makes VARUNA-SDS different

VARUNA-SDS applies an idea from radio communications called **Software-Defined Radio (SDR)**: instead of hardware generating the signal, software running on a microcontroller generates any waveform it wants, digitally.

**The key innovation:**

| Traditional Sonar | VARUNA-SDS |
| :--- | :--- |
| Fixed crystal oscillator at 40 kHz | Microcontroller generates any wave via software |
| Cannot change frequency without hardware swap | Frequency, shape, and timing set via UART command |
| Simple rectangular pulse | Shaped pulses with windowing (Tukey/Hann) |
| Range resolution: ~4 metres | Range resolution: **7.6 cm** (using LFM chirp + matched filter) |
| Fails at thermoclines | Can adapt waveform to penetrate stratified water |

---

## 4. Core concepts explained simply

### 4.1 Direct Digital Synthesis (DDS) & DMA Streaming

Imagine you want to synthesize an arbitrary sine wave or chirp. Rather than computing expensive trigonometric operations in real-time, the system uses a **32-bit Fixed-Point Phase Accumulator** and a pre-computed 1024-entry Look-Up Table (LUT):

```
Phase Accumulator (32-bit integer)  ──►  LUT Index (Top 10-bits)  ──►  1024-Entry Sine Table
                 ▲                                                             │
                 └── [ + Phase Increment = (f × 2^32) / Fs ]                   ▼
                                                                        Quantized 8-Bit DAC Sample
                                                                               │
                                                                               ▼
                                                                     I2S DMA Descriptor Ring
                                                                               │
                                                                               ▼
                                                                     Internal DAC (GPIO25)
```

1. **Phase Accumulator:** Every clock tick, the 32-bit accumulator advances by `phase_inc`. Overflow wraps at $2^{32}$, giving exact $2\pi$ mathematical periodicity with zero cumulative frequency drift.
2. **Hardware DMA Streaming:** The computed waveform buffer is transferred to the internal DAC via **I2S DMA descriptors**, freeing the CPU from timing-critical pin-toggling loops.
3. This is implemented in [`firmware/src/dds_engine.c`](firmware/src/dds_engine.c) and [`firmware/src/hal_esp32_dac.c`](firmware/src/hal_esp32_dac.c).

### 4.2 LFM Chirp vs CW Ping

- **CW Ping** (Continuous Wave): A burst of a single, constant frequency (40 kHz). Simple. Like a bat's click.
- **LFM Chirp** (Linear Frequency Modulation): The frequency sweeps from 35 kHz to 45 kHz in a smooth ramp over the pulse duration. Like a bird's "tweet" going from low to high.

The chirp has a huge advantage: when you correlate (cross-multiply) the received echo against the transmitted chirp template, all the signal energy **compresses into a sharp spike**. This is **pulse compression** and it makes range resolution 50× better.

```
CW Ping echo:       ~~~~~~~~~~~~~~~~~~~~  (wide, smeared blob — hard to pinpoint)
LFM Chirp echo:     |                    (sharp spike — exact range, 7.6 cm accuracy)
```

### 4.3 The LC Reconstruction Filter

The PAM8302 amplifier is a **Class-D** device — it doesn't output a smooth sine wave; it outputs a high-frequency pulse train at 250 kHz. If you fed this directly into the piezo transducer, you'd be transmitting noise at 250 kHz, not your 40 kHz signal.

The LC filter (100 µH inductor + 100 nF capacitor) acts as a **low-pass filter**: it passes frequencies below ~35–50 kHz and blocks everything above. This strips out the 250 kHz switching noise and leaves only the clean acoustic sine wave.

```
PAM8302 output:  __|‾|_|‾|_|‾|_   (250 kHz square wave + 40 kHz content)
After LC filter:     ∿∿∿∿∿∿∿        (smooth 40 kHz sine wave only)
```

### 4.4 The Piezoelectric Transducer

A **piezoelectric disc** converts electrical voltage into physical vibration (and vice versa). When you apply a 40 kHz sine wave voltage to it, it physically vibrates 40,000 times per second, pushing the water and creating a 40 kHz acoustic pressure wave.

The disc we use is extracted from a **JSN-SR04T** waterproof ultrasonic module. The JSN-SR04T contains a microcontroller that locks it to digital trigger/echo mode — so we desolder the raw piezo disc from the probe and drive it directly with our analog signal.

---

## 5. Hardware you need to buy

### 5.1 Complete Bill of Materials (BOM)

| # | Part | Why you need it | Where to buy | Cost |
| :- | :--- | :--- | :--- | :---: |
| 1 | **ESP32 Dev Board** | The brain — generates all waveforms in software | [Robu.in](https://robu.in) | ₹220 |
| 2 | **PAM8302 Class-D Amplifier Module** | Boosts the tiny DAC voltage to drive the piezo disc | [ElectronicsComp](https://electronicscomp.com) | ₹95 |
| 3 | **JSN-SR04T Waterproof Ultrasonic Module** | Contains the 40 kHz piezo disc we need (desolder it) | [Robu.in](https://robu.in) / Amazon | ₹320 |
| 4 | **100 µH Inductor (radial, ≥0.5A)** | Part of LC reconstruction filter | Local electronics shop | ₹15 |
| 5 | **100 nF Film Capacitor (100V rated)** | Part of LC reconstruction filter | Local electronics shop | ₹20 |
| 6 | **0.1 µF Ceramic Capacitor** | AC-coupling capacitor between ESP32 DAC and PAM8302 | Local electronics shop | ₹5 |
| 7 | **18650 Li-ion Battery Cell** | Provides 3.7V power | Local market / Robu.in | ₹80 |
| 8 | **TP4056 Li-ion Charger Module** | Safely charges the 18650 cell | Robu.in | ₹40 |
| 9 | **5V Buck Converter Module (MT3608 / XL6009)** | Steps up 3.7V battery to 5V for ESP32 + PAM8302 | Robu.in | ₹25 |
| 10 | **Transparent Acrylic Box / Large Bucket** | Water tank for testing | Hardware store | ₹80 |
| 11 | **Jumper Wires, Header Pins** | Connections | Local market | ₹40 |
| 12 | **Small Toggle Switch** | Power on/off | Local market | ₹10 |
| | **Total** | | | **~₹930** |

> **Tip:** Buy 2 of the JSN-SR04T module in case you damage the piezo disc during desoldering.

---

## 6. Tools you need

| Tool | Purpose |
| :--- | :--- |
| Soldering Iron (30–40W, fine tip) | Desoldering JSN-SR04T, wiring connections |
| Solder wire (0.8 mm, 60/40 tin-lead) | Making electrical connections |
| Desoldering pump / wick | Removing solder from JSN-SR04T |
| Multimeter | Verifying voltages before connecting to ESP32 |
| USB-A to Micro-USB cable | Flashing firmware to ESP32 |
| Laptop / Desktop (Windows, Mac, or Linux) | Software setup, firmware flashing |
| Small breadboard | Initial prototyping before soldering permanently |
| Wire cutters & strippers | Preparing wires |

---

## 7. Step-by-step hardware assembly

### Step 1: Extract the Piezo Transducer from JSN-SR04T

> ⚠️ **Be patient — the piezo disc is fragile. Don't overheat it.**

1. The JSN-SR04T has two parts: a **blue processing PCB** and a **waterproof aluminum probe** connected by a 2-wire coaxial cable.
2. Heat the solder joints connecting the 2-wire cable to the blue PCB at low iron temperature (≤320°C).
3. Unsolder the cable from the blue PCB. **Use only the raw probe + its 2 wires** going forward. Discard the blue PCB.
4. Strip the probe cable wires: you will see a **center conductor** (signal) and a **braided shield** (ground).
5. Verify continuity: place multimeter probes on the 2 wire ends. You should see ~1–10 kΩ (piezo capacitance).

```
JSN-SR04T Probe:
  [Aluminum housing] ─── [Piezo disc inside] ─── [2-wire cable]
                                                     ↓
                                          Center = Signal (drive)
                                          Shield = Ground (GND)
```

### Step 2: Build the LC Reconstruction Filter

On a small breadboard or piece of perfboard:

```
PAM8302 OUT+  ──[ 100µH Inductor ]──────────────── Piezo+ (center wire)
                                        |
                                    [100nF cap]
                                        |
PAM8302 OUT-  ──────────────────────────────────── Piezo- (shield wire)
               (same GND rail)
```

> For best results, use **film capacitor** (orange/yellow), not ceramic. Film capacitors are more linear at high frequency.

### Step 3: Wire ESP32 to PAM8302

| ESP32 Pin | PAM8302 Pin | Notes |
| :--- | :--- | :--- |
| GPIO25 (DAC1) | A_IN+ (via 0.1µF cap) | AC-couple to block DC offset |
| GND | A_IN− | Common ground |
| GPIO26 | SD (Shutdown) | HIGH = amplifier on, LOW = muted |
| 5V | VDD | Power rail for PAM8302 |
| GND | GND | — |

> **AC-coupling:** Place a 0.1 µF ceramic cap in series between GPIO25 and the PAM8302 IN+ pin. This blocks the DC bias of the ESP32 DAC (which sits at ~1.65V) and only passes the AC waveform to the amplifier.

### Step 4: Power Wiring

```
18650 Cell (+) ──► Toggle Switch ──► TP4056 IN+ ──► Buck Converter IN+
18650 Cell (−) ──────────────────► TP4056 IN− ──► Buck Converter IN−
Buck Converter OUT+ (5V) ──► ESP32 VIN, PAM8302 VDD
Buck Converter OUT− (GND) ──► ESP32 GND, PAM8302 GND, LC Filter GND
```

Set the buck converter output to exactly **5.0V** using the trimmer potentiometer before connecting anything. Verify with a multimeter.

---

## 8. Software setup on your computer

### 8.1 Install Python (if not already installed)

1. Go to [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Download Python 3.11 or 3.12.
3. During install, **check "Add Python to PATH"**.
4. Open a terminal/command prompt and confirm: `python --version`

### 8.2 Clone the Repository

```bash
# If you have git installed:
git clone https://github.com/gangasagar5928/VARUNA-SDS.git
cd VARUNA-SDS

# Or download the ZIP from GitHub and extract it.
```

### 8.3 Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs `numpy`, `scipy`, and `matplotlib` — the libraries used for signal processing simulation.

### 8.4 Install PlatformIO (for firmware flashing)

```bash
pip install platformio
```

PlatformIO automatically downloads the correct ESP32 compiler and libraries — no manual Arduino IDE setup needed.

---

## 9. Flashing firmware to ESP32

### 9.1 Connect ESP32 to your laptop

- Use a Micro-USB cable.
- On Windows: Device Manager should show a new COM port (e.g., `COM5`).
- On Linux/Mac: You'll see `/dev/ttyUSB0` or `/dev/cu.usbserial-...`

### 9.2 Build and flash

```bash
pio run -d firmware -e esp32dev -t upload
```

PlatformIO will:
1. Download ESP32 toolchain (first-time only, ~300 MB).
2. Compile all firmware source files in `firmware/src/`.
3. Flash the binary to ESP32 over USB.

You should see output ending with:
```
Linking .pio/build/esp32dev/firmware.elf
Checking size .pio/build/esp32dev/firmware.elf
Writing at 0x00010000... (100 %)
Hash of data verified.
```

### 9.3 Open the serial monitor

```bash
pio device monitor -b 115200
```

You should see the VARUNA-SDS boot banner:
```
==============================================
VARUNA-SDS: Software-Defined Sonar Payload
Adaptive Subsea Acoustic Waveform Synthesis
==============================================
[STATE] SYSTEM_INIT Complete. Entering IDLE_STANDBY.
```

---

## 10. Running the Python simulation

The simulation suite runs entirely on your laptop — **no hardware required**. It lets you verify the signal math before building anything.

```bash
# Full end-to-end demo
python simulation/run_demo.py
```

**Expected output:**
```
======================================================================
 VARUNA-SDS: Software-Defined Sonar Simulation Suite
 'Adaptive Subsea Acoustic Waveform Synthesis for AUVs'
======================================================================

[1] ACOUSTIC ENVIRONMENT:
    - Sound Speed in Seawater (Mackenzie): 1521.54 m/s
    - Target Range: 15.0 m (Round-Trip: 30.0 m)
    - Round-Trip Acoustic Transmission Loss: 29.90 dB

[2] SYNTHESIS & MATCHED FILTER ANALYSIS:
    +---------------------------+-------------------+-------------------+
    | Metric                    | Mode A (CW 40kHz) | Mode B (LFM Chirp)|
    +---------------------------+-------------------+-------------------+
    | Matched Filter Gain       | 0.00           dB | 16.99          dB |
    | Range Resolution (Delta R)| 380.4          cm | 7.6            cm |
    +---------------------------+-------------------+-------------------+

[3] PAM8302 CLASS-D LC RECONSTRUCTION FILTER:
    - PWM Carrier Suppression Margin: 33.43 dB (>20 dB Target MET)
```

**What each simulation file does:**

| File | What it simulates |
| :--- | :--- |
| `simulation/dds_synthesizer.py` | Generates CW and LFM waveforms in software, quantizes to 8-bit DAC values |
| `simulation/acoustic_channel.py` | Simulates ocean: computes sound speed (Mackenzie formula), transmission loss (Thorp absorption), and multipath reflections |
| `simulation/matched_filter.py` | Applies matched filter (cross-correlation) to the received echo and computes range resolution |
| `simulation/lc_filter_sim.py` | Computes the frequency response of the 100 µH + 100 nF LC filter |
| `simulation/run_demo.py` | Runs all of the above and prints a comparison table |

---

## 11. Testing and verifying the build

### 11.1 Run automated unit tests

```bash
python tests/test_dds.py -v
```

**Expected output:**
```
test_acoustic_channel_sound_speed ... ok
test_cw_synthesis_frequency_accuracy ... ok
test_lc_reconstruction_filter_carrier_suppression ... ok
test_lfm_chirp_sweep_properties ... ok
test_matched_filter_pulse_compression_gain ... ok

----------------------------------------------------------------------
Ran 5 tests in 0.003s

OK
```

**What each test checks:**

| Test Name | What it verifies |
| :--- | :--- |
| `test_cw_synthesis_frequency_accuracy` | 40 kHz peak is within ±100 Hz of target |
| `test_lfm_chirp_sweep_properties` | Chirp energy is concentrated in the 35–45 kHz band |
| `test_matched_filter_pulse_compression_gain` | Pulse compression gain = 10·log10(50) ≈ 17 dB |
| `test_lc_reconstruction_filter_carrier_suppression` | LC filter attenuates 250 kHz carrier by > 20 dB |
| `test_acoustic_channel_sound_speed` | Mackenzie formula gives 1500–1550 m/s for ocean conditions |

### 11.2 Verify hardware with a multimeter (before water test)

| Check | Expected value | Pin |
| :--- | :--- | :--- |
| Buck converter output | 5.00 V ± 0.1 V | Converter OUT+ vs OUT− |
| ESP32 idle DAC voltage | ~1.65 V DC | GPIO25 vs GND |
| PAM8302 SD pin (standby) | < 0.5 V (muted) | GPIO26 |
| PAM8302 SD pin (transmitting) | ~3.3 V (enabled) | GPIO26 |

---

## 12. Controlling VARUNA-SDS over serial

Connect ESP32 via USB and open a serial terminal at **115200 baud, 8N1** (e.g., PlatformIO Monitor, Arduino Serial Monitor, PuTTY, or `screen`).

### Full Command Reference

```
PING                          Transmit a single sonar pulse immediately

SET_MODE 0                    Switch to Mode A: CW Ping (40 kHz mono)
SET_MODE 1                    Switch to Mode B: LFM Chirp
SET_MODE 2                    Set to STANDBY (amplifier muted)

SET_CW_FREQ 40000             Set CW frequency to 40 kHz (10000–100000 valid)
SET_CHIRP 35000 45000         Set LFM chirp from 35 kHz to 45 kHz
SET_DURATION 5000             Set pulse width to 5000 µs (= 5 ms)
SET_PRI 200                   Set Pulse Repetition Interval to 200 ms (5 Hz)
SET_WINDOW 0                  Rectangular window (hard edges)
SET_WINDOW 1                  Hann window (smooth, low sidelobe)
SET_WINDOW 2                  Tukey window (flat-top with tapered edges) ← recommended
SET_AUTO 1                    Auto-transmit at PRI interval
SET_AUTO 0                    Manual trigger only

GET_CONFIG                    Print current configuration
STATUS                        Same as GET_CONFIG
HELP                          Print all available commands
```

### Example session

```
> SET_CHIRP 35000 45000       # Configure LFM sweep
> SET_DURATION 8000           # 8 ms pulse
> SET_WINDOW 2                # Tukey windowing
> SET_PRI 500                 # Ping every 500 ms
> SET_AUTO 1                  # Start continuous pinging
> GET_CONFIG                  # Verify settings
--- VARUNA-SDS CONFIG ---
Mode: LFM Chirp (Mode B)
Chirp: 35000 Hz -> 45000 Hz (BW = 10000 Hz)
Pulse Duration: 8000 us
PRI: 500 ms (Freq: 2.00 Hz)
Window: Tukey
Auto-Trigger: ENABLED
```

---

## 13. Water tank test procedure

> ⚠️ **Do not submerge the ESP32 or electronics.** Only the probe end of the piezo disc goes in water. Keep all boards dry.

### Setup

1. Fill a bucket or acrylic box with water (at least 30 cm deep).
2. Suspend the piezo disc vertically, submerged to at least 5 cm depth.
3. Keep all electronics boards outside the bucket.
4. Tape or zip-tie a solid reflector (metal plate or ceramic tile) at a known distance underwater (e.g., 15 cm from the transducer).

### Transmit test

1. Flash firmware and open serial monitor.
2. Send: `SET_MODE 0` then `PING`.
3. Switch to chirp: `SET_MODE 1` then `PING`.
4. If using an oscilloscope or receiving hydrophone, probe the transducer terminals to inspect the 40 kHz sine wave bursts.

### What to observe

- **Acoustic inaudibility note:** 40 kHz is **ultrasonic** (human hearing limit is ~20 kHz) — you will **not** hear an audible tone with human ears.
- **Visual confirmation:** Submerge the transducer near the water surface; during high-amplitude bursts you can observe fine acoustic surface ripples or cavitation disturbances.
- **Electronic verification:** Connect an oscilloscope across the piezo wires to observe the clean sinusoidal voltage burst without 250 kHz Class-D carrier switching artifacts.
- The pre-warm delay (100 µs) before each burst prevents pop transients and stabilizes the Class-D power stage.

---

## 14. Troubleshooting guide

| Problem | Likely cause | Fix |
| :--- | :--- | :--- |
| Serial monitor shows nothing | Wrong baud rate | Set terminal to exactly 115200 baud, 8N1 |
| `pio run` fails: "device not found" | ESP32 not recognized | Install CP2102 / CH340 USB driver |
| ESP32 resets continuously | Insufficient power | Use a proper 5V 1A supply, not a USB hub |
| PAM8302 gets very hot | Load impedance too low | Check piezo disc is connected; add series 8 Ω resistor for testing |
| No sound from piezo | PAM8302 SD pin stuck LOW | Verify GPIO26 goes HIGH during PING command |
| Sound is buzzy / distorted | LC filter wired wrong | Double-check L and C positions; L is in series, C is in parallel |
| Python `ModuleNotFoundError` | Dependencies not installed | Run `pip install -r requirements.txt` |
| CI pipeline fails | PlatformIO build error | Check `firmware/platformio.ini` for correct board ID |
| Piezo broke during desoldering | Overheating | Use desoldering braid at low heat; work quickly |

---

## 15. Understanding the acoustic numbers

### Why 40 kHz?

Human hearing goes up to ~20 kHz. The JSN-SR04T piezo disc is resonant at 40 kHz — its mechanical structure vibrates most efficiently at this frequency. Going above or below reduces acoustic output power. For the student prototype, 40 kHz is the sweet spot. Production Tonpilz transducers can resonate from 3 kHz to 200 kHz.

### What is "Source Level 183 dB re 1µPa @ 1m"?

Underwater acoustic amplitude is measured in **decibels relative to 1 micropascal at 1 metre** (dB re 1µPa @ 1m). This is the **Source Level (SL)**. 183 dB is typical for a small piezoceramic disc at 2.5W drive power. This is much higher than air — underwater dB reference is 1 µPa vs 20 µPa in air, so don't compare them directly.

### Why does LFM chirp give 7.6 cm resolution?

Range resolution is determined by the bandwidth, not the pulse duration:

```
ΔR = c / (2 × B)
   = 1521 m/s / (2 × 10,000 Hz)
   = 0.076 m  →  7.6 cm
```

Where:
- `c` = sound speed in seawater (~1521 m/s)
- `B` = chirp bandwidth (35 kHz to 45 kHz = 10,000 Hz)

A CW ping at 40 kHz has a bandwidth of only ~200 Hz (set by pulse duration), giving:

```
ΔR = 1521 / (2 × 200) = 3.8 m
```

This is why **LFM chirp is 50× more accurate in range resolution** compared to a CW ping of the same duration.

### What is the matched filter processing gain of +17 dB?

The matched filter cross-correlates the received signal with the transmitted replica. All the signal energy compresses into a single sharp peak. The peak is `B×T = 10,000 × 0.005 = 50` times the noise level:

```
Processing Gain = 10 × log₁₀(B × T) = 10 × log₁₀(50) = 16.99 dB ≈ +17 dB
```

This means you can detect echoes **50× weaker** than what a CW ping could detect — allowing much longer range detection.

---

## 16. Scaling to production

| Aspect | Student Prototype | Production System |
| :--- | :--- | :--- |
| Compute | ESP32 / STM32F103 | Xilinx Zynq-7000 / Spartan-7 FPGA |
| DAC | Internal 8-bit MCU DAC (500 kSPS) | External 16-bit 1 MSPS Dual DAC |
| Amplifier | PAM8302 2.5W Class-D | Class-D / Class-H high-voltage bridge |
| Transducer | 40 kHz Piezo disc from JSN-SR04T | PZT-5H Tonpilz / Barrel-Stave Projector |
| Power | 18650 Li-ion + TP4056 | AUV 24V main bus + DC-DC isolation |
| Housing | Acrylic bucket | IP68 Anodized Aluminum 6061 cylinder |
| Communication | UART over USB | UART/RS485, SPI, CAN bus |
| Cost | ₹935 / ~$11 USD | ₹25,000+ / ~$300 USD |
| Operating depth | Surface / shallow tank | 100 m (IP68 rated) |

---

## 17. Glossary of terms

| Term | Plain-English Meaning |
| :--- | :--- |
| **AUV** | Autonomous Underwater Vehicle — a robot submarine that operates without a human pilot |
| **CW Ping** | Continuous Wave Ping — a burst of a single fixed frequency |
| **DAC** | Digital-to-Analog Converter — chip that converts numbers from the microcontroller into a voltage |
| **DDS** | Direct Digital Synthesis — technique for generating arbitrary waveforms using a Look-Up Table |
| **DMA** | Direct Memory Access — hardware that copies data from memory to DAC without using the CPU |
| **FFT** | Fast Fourier Transform — mathematical tool that shows which frequencies are present in a signal |
| **IP68** | International Protection Rating — sealed against full water immersion (6 = dust-tight, 8 = >1m water) |
| **LFM Chirp** | Linear Frequency Modulation — a pulse that sweeps frequency linearly over time |
| **LUT** | Look-Up Table — pre-computed array of sine wave values stored in memory |
| **Matched Filter** | Signal processing technique that maximises SNR by correlating received signal with a known template |
| **MCU** | Microcontroller Unit — a small computer chip (ESP32, STM32) that runs firmware |
| **PAM8302** | A small Class-D audio amplifier IC — used here to drive the piezo transducer |
| **PRI** | Pulse Repetition Interval — time gap between successive sonar pulses |
| **PZT** | Lead Zirconate Titanate — the ceramic material used in high-quality piezoelectric transducers |
| **SDR** | Software-Defined Radio — system where signal processing happens in software instead of hardware |
| **SNR** | Signal-to-Noise Ratio — how much stronger the signal is compared to background noise |
| **Thermocline** | A sharp temperature boundary layer in the ocean where acoustic sound bends |
| **Tonpilz** | A type of piezoelectric transducer shaped like a mushroom, used in professional sonar |
| **Transducer** | A device that converts one type of energy to another — here, electrical energy → sound |

---

*VARUNA-SDS is an open-source project. Contributions, improvements, and deployment stories are welcome.*

*Built for the Ministry of Earth Sciences Smart India Hackathon.*
