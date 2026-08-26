# Hardware Integration & Schematic Guide
## VARUNA-SDS: Software-Defined Sonar Transmitter

---

## 1. System Interconnect Block Diagram

```
+-------------------------------------------------------------------------------+
|                             AUV / Host Controller                             |
|                               (Serial CLI / SPI)                              |
+---------------------------------------+---------------------------------------+
                                        | UART (TX: GPIO17, RX: GPIO16 @ 115200)
                                        v
+-------------------------------------------------------------------------------+
|                       Compute & Synthesis Core (ESP32)                        |
|                                                                               |
|   +-------------------+       +--------------------+      +---------------+   |
|   | DDS Engine        | ----> | DMA Ping-Pong      | ---> | 8-bit DAC     |   |
|   | (LUT Synth / LFM) |       | Circular Buffers   |      | (GPIO25 / CH1)|   |
|   +-------------------+       +--------------------+      +-------+-------+   |
|                                                                   |           |
|   +------------------------------------------------+              |           |
|   | Amp Shutdown / Enable Line (GPIO 26)           |              |           |
+---+------------------------------------------------+--------------+-----------+
                               |                                    | Analog Out
                               | Active Low SD_N                    | (0.1V - 3.2V)
                               v                                    v
+-------------------------------------------------------------------------------+
|                   Acoustic Power Amplifier Stage (PAM8302)                    |
|                                                                               |
|   * Class-D Single-Channel Mono Bridge Tied Load (BTL)                        |
|   * Switching Frequency: ~250 kHz                                             |
|   * Max Output Power: 2.5W into 4 Ohm @ 5V                                    |
|   * Power Input: 5V Regulated (Boosted from 18650 3.7V)                       |
|   * Pinout:                                                                   |
|       - VIN+ : AC-Coupled from MCU DAC (0.1uF series cap)                     |
|       - VIN- : Analog Ground (GND)                                            |
|       - SD   : Connected to MCU GPIO26 (Mute when not pinging)                |
|       - OUT+ / OUT- : Differential PWM output                                 |
+---------------------------------------+---------------------------------------+
                                        | Differential PWM (~250 kHz carrier)
                                        v
+-------------------------------------------------------------------------------+
|                      LC Reconstruction & Demodulation Filter                   |
|                                                                               |
|                      L1: 100 uH (High-Current Ferrite)                        |
|        OUT+ o---------\/\/\/\/\-------+-------o Piezo Terminal A              |
|                                       |                                       |
|                                    +--+--+                                    |
|                                    |     | C1: 100 nF                         |
|                                    |     | (Film / X7R Ceramic)               |
|                                    +--+--+                                    |
|                                       |                                       |
|        OUT- o---------\/\/\/\/\-------+-------o Piezo Terminal B              |
|                      L2: 100 uH (High-Current Ferrite)                        |
|                                                                               |
+---------------------------------------+---------------------------------------+
                                        | Smooth 35 kHz - 45 kHz Acoustic Sine
                                        v
+-------------------------------------------------------------------------------+
|                 Bare Waterproof 40 kHz Piezoelectric Transducer               |
|                       (Desoldered from JSN-SR04T probe)                       |
+-------------------------------------------------------------------------------+
```

---

## 2. LC Filter Engineering Calculations

The PAM8302 Class-D amplifier produces a high-frequency pulse-width modulated (PWM) switching waveform at \(f_{sw} \approx 250\text{ kHz}\). 
To drive the narrow-band piezoelectric transducer with minimum thermal losses and prevent high-frequency EMI in water:

### 2.1 Cutoff Frequency (\(f_c\))
Using a symmetrical 2nd-order differential low-pass filter:
$$f_c = \frac{1}{2 \pi \sqrt{L_{eq} \cdot C}}$$

Where:
- \(L_{eq} = L_1 + L_2 = 100\,\mu\text{H} + 100\,\mu\text{H} = 200\,\mu\text{H}\)
- \(C = 100\text{ nF}\)

$$f_c = \frac{1}{2 \pi \sqrt{200 \times 10^{-6} \times 100 \times 10^{-9}}} = \frac{1}{2 \pi \sqrt{2 \times 10^{-11}}} \approx 35.59\text{ kHz} \dots 50.3\text{ kHz (single-ended equivalent)}$$

For differential topology with \(L = 100\,\mu\text{H}\) on each leg and bridging capacitor \(C = 100\text{ nF}\):
- Passband: \(20\text{ kHz} - 45\text{ kHz}\) (Insertion loss < 0.8 dB)
- Stopband Attenuation at \(250\text{ kHz}\) carrier: **> 24 dB suppression**

---

## 3. Transducer Extraction Guide (JSN-SR04T)

1. **Safety & Tool Prep**: Low-power soldering iron (30W-40W), flux, desoldering pump or copper braid.
2. **Identification**: JSN-SR04T has two components:
   - External waterproof aluminum ultrasonic probe (contains the bare piezo element).
   - Blue processing PCB (contains STC MCU and comparator).
3. **Desoldering**:
   - The probe connects via a 2-pin coaxial cable to the blue PCB.
   - Unsolder the 2-pin header/leads directly from the PCB.
   - DO NOT route audio signals through the on-board STC microcontroller. Connect directly to the LC filter output terminals.
4. **Polarity Check**: Piezo discs are non-polar for AC drive, but shield conductor should go to ground/OUT- side for noise shielding.

---

## 4. Pin Mapping

| ESP32 Pin | Function | Connects To | Notes |
| :--- | :--- | :--- | :--- |
| **GPIO25 (DAC1)** | Analog Synthesizer Out | PAM8302 `A_IN+` | AC coupled via 0.1uF ceramic cap |
| **GND** | Ground Reference | PAM8302 `A_IN-`, Power GND | Common ground star connection |
| **GPIO26** | Amp Mute/Shutdown (`SD_N`) | PAM8302 `SD` Pin | Active Low; HIGH = Enable, LOW = Standby Mute |
| **GPIO16 (RX2)** | Telemetry In | Host/AUV TX | 115200 baud, 8N1 |
| **GPIO17 (TX2)** | Telemetry Out | Host/AUV RX | 115200 baud, 8N1 |
| **5V Rail** | Power Supply | PAM8302 `VDD` | Decoupled with 470uF low-ESR electrolytic |
| **3.3V Rail** | MCU Power | ESP32 VCC | Regulated |
