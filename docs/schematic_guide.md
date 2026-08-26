# Hardware Integration & Schematic Guide
## VARUNA-SDS: Software-Defined Sonar Transmitter

![VARUNA-SDS Hardware Layer Architecture](../assets/varuna_sds_exploded_view.jpg)

> **v1.1 Correction:** LC filter redesigned from 100 µH + 100 nF (fc ≈ 35.59 kHz — **below carrier, critical bug**) to **68 µH + 150 nF (fc ≈ 49.8 kHz — above carrier, correct)**.

---

## 1. System Interconnect Block Diagram

```
+-------------------------------------------------------------------------------+
|                           AUV / Host Controller                               |
|                             (Serial CLI / RS485)                              |
+---------------------------------------+---------------------------------------+
                                        | UART (TX: GPIO17, RX: GPIO16 @ 115200)
                                        v
+-------------------------------------------------------------------------------+
|                     Compute & Synthesis Core (ESP32)                          |
|                                                                               |
|   DDS Engine (LUT/LFM) → DMA Ping-Pong Buffers → 8-bit DAC (GPIO25)          |
|   Amp Enable Line (GPIO26 HIGH = run, LOW = muted)                            |
+---+----------------------------------------------------+----------------------+
    |                                                    | Analog Out (0–3.3V)
    | GPIO26 (Amp Mute)                                  | AC-Coupled 0.1µF cap
    v                                                    v
+-------------------------------------------------------------------------------+
|                  PAM8302 Class-D Audio Power Amplifier                        |
|                                                                               |
|  ⚠ PROTOTYPE NOTE: PAM8302 is rated 20 Hz – 20 kHz (audio band).            |
|  Driving at 40 kHz is outside its datasheet spec — output power drops        |
|  sharply above 20 kHz. Acceptable for hackathon prototype; in production      |
|  replace with a dedicated ultrasonic driver IC (e.g., TC1427, 200 kHz,       |
|  ±1.5A complementary output, or equivalent half-bridge MOSFET driver).       |
|                                                                               |
|  VDD: 5V | SD: GPIO26 | IN+: ESP32 GPIO25 (via 0.1µF) | IN-: GND             |
+---------------------------------------+---------------------------------------+
                                        | Differential PWM (~250 kHz switching)
                                        v
+-------------------------------------------------------------------------------+
|                LC Reconstruction Filter — v1.1 CORRECTED VALUES               |
|                                                                               |
|   L = 68 µH (per leg), C = 150 nF (shunt to GND), fc ≈ 49.8 kHz             |
|                                                                               |
|   OUT+ ──[L1: 68µH]──────────────────────── Piezo Terminal A                 |
|                             |                                                 |
|                          [150nF]  ← shunt cap to GND                         |
|                             |                                                 |
|   GND  ─────────────────────┴──────────────── GND                            |
|                                                                               |
|   OUT- ──[L2: 68µH]──────────────────────── Piezo Terminal B                 |
|                             |                                                 |
|                          [150nF]  ← shunt cap to GND (symmetric leg)         |
|                             |                                                 |
|   GND  ─────────────────────┘                                                 |
+---------------------------------------+---------------------------------------+
                                        | Clean 35–45 kHz acoustic sine wave
                                        v
+-------------------------------------------------------------------------------+
|            Bare Waterproof 40 kHz Piezoelectric Transducer                   |
|                (Desoldered from JSN-SR04T probe)                              |
|                                                                               |
|  ⚠ TRANSDUCER NOTE: This is a consumer-grade component. Impedance at 40 kHz  |
|  in water is uncharacterized. For production, use a calibrated PZT-5H         |
|  Tonpilz transducer with a measured impedance model and a tuned matching      |
|  network (KLM model recommended).                                             |
+-------------------------------------------------------------------------------+
```

---

## 2. LC Filter Design — v1.1 Corrected Calculation

### Why the original design was wrong

The v1.0 design used 100 µH + 100 nF in a differential bridge topology:

```
Leq (differential) = L1 + L2 = 100µH + 100µH = 200 µH
fc = 1 / (2π√(200e-6 × 100e-9)) = 35.59 kHz
```

**This is below the 40 kHz carrier — the filter was attenuating the sonar signal in its own stopband.**

### Corrected Design — Single-Ended Per Leg

Each output leg (OUT+ and OUT−) has its own independent LC section:

```
fc = 1 / (2π√(L × C))
   = 1 / (2π√(68e-6 × 150e-9))
   = 1 / (2π × 3.194e-6)
   = 49.83 kHz
```

| Frequency | Filter Response | Meaning |
| :--- | :--- | :--- |
| **40 kHz** (sonar carrier) | **+6.1 dB** (near-resonance peaking) | ✅ Signal passes — boosted by resonance |
| **250 kHz** (PAM8302 switching) | **−27.7 dB** | ✅ PWM carrier suppressed |
| **Carrier suppression margin** | **33.8 dB** | ✅ Well above 20 dB spec |

> The +6.1 dB peaking at 40 kHz is the expected behaviour of an LC tank near resonance. The sonar signal is not attenuated — it is slightly amplified. This is harmless and can be reduced by adding a small series resistor (≈10–22 Ω) to increase damping (Q).

### Component selection notes

| Component | Value | Spec requirement | Source |
| :--- | :--- | :--- | :--- |
| Inductor L1, L2 | **68 µH** | Ferrite core, ≥ 500 mA rated current, self-resonance > 500 kHz | Local shop / LCSC |
| Capacitor C | **150 nF** | Film type (not ceramic) for linearity at 40 kHz; 50V minimum rating | Local shop / LCSC |
| Damping resistor (optional) | 10–22 Ω | Reduces Q from 2.35 to <1 (flat passband); place in series before each inductor | Optional |

---

## 3. Known Design Gaps (v1.0 Prototype)

| Gap | Description | Production Fix |
| :--- | :--- | :--- |
| **No Receive Path** | VARUNA-SDS v1.0 is transmit-only. No hydrophone, preamp, or ADC digitization. | Add hydrophone preamp + 16-bit ADC (e.g., ADS8681) on a v2.0 Rx board |
| **PAM8302 off-spec** | Rated to 20 kHz audio; used at 40 kHz ultrasonic | Replace with TC1427 or dedicated H-bridge ultrasonic driver |
| **8-bit DAC, 12.5 samp/cycle** | ~-40 dBc SFDR; visible harmonic spurs | External 16-bit 1 MSPS DAC (AD9767 / DAC8830) → ~-80 dBc |
| **Uncalibrated transducer** | JSN-SR04T piezo: impedance at 40 kHz in water unknown | PZT-5H Tonpilz with KLM impedance model + matching network |
| **Depth rating** | Acrylic prototype: shallow tank only. 100 m claim = production hull target only | IP68 anodized 6061 aluminium housing with O-ring seals; hydrostatic test required |
| **DDS SFDR not characterised** | LUT size: 1024 points; samp/cycle at 40 kHz: 12.5 | Measure THD with spectrum analyser; target < -50 dBc for final design |

---

## 4. Pin Mapping

| ESP32 Pin | Function | Connects To | Notes |
| :--- | :--- | :--- | :--- |
| **GPIO25 (DAC1)** | Analog Synthesizer Out | PAM8302 IN+ | AC coupled via 0.1 µF ceramic cap |
| **GND** | Ground Reference | PAM8302 IN−, Power GND | Common star-ground connection |
| **GPIO26** | Amp Mute/Enable (SD\_N) | PAM8302 SD pin | HIGH = Enable, LOW = Standby/Mute |
| **GPIO16 (RX2)** | Telemetry In | Host/AUV TX | 115200 baud, 8N1 |
| **GPIO17 (TX2)** | Telemetry Out | Host/AUV RX | 115200 baud, 8N1 |
| **5V Rail** | Amp Power | PAM8302 VDD | Decoupled 470 µF low-ESR electrolytic |
| **3.3V Rail** | MCU Power | ESP32 VCC | From on-board LDO regulator |

---

## 5. Transducer Extraction Guide (JSN-SR04T)

> ⚠ Buy 2 units in case of damage during desoldering. Work at ≤ 320°C.

1. Identify components: blue processing PCB (STC MCU inside) + external waterproof aluminium probe (piezo inside), joined by 2-wire coaxial cable.
2. Unsolder the 2-wire cable from the **blue PCB** only. Discard the blue PCB.
3. Strip the probe cable: center conductor = signal (Piezo+), braid = ground (Piezo−).
4. Verify with multimeter across the two wires: expect 1–10 kΩ (piezo capacitance + leakage).
5. Connect center wire to LC filter output node (after inductors), braid to GND.

> **Production note:** The JSN-SR04T piezo disc has unknown impedance in water at 40 kHz. Any production design must characterize Rp, Cp, Rm (motional parameters) using an impedance analyser (e.g., Keysight E4990A) and design a matching network accordingly.
