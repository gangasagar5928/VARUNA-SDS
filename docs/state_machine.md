# Execution State Machine & Timing Specifications

## State Flow Diagram

```
 +---------------------------------------------------------+
 |                       POWER_ON                          |
 |                 (Cold boot / System start)              |
 +----------------------------+----------------------------+
                              |
                              v
 +---------------------------------------------------------+
 |                      SYSTEM_INIT                        |
 |   - Init Hardware Timers & DMA ring buffers             |
 |   - Init DAC Controller @ 500 kSPS                      |
 |   - Init UART Telemetry Engine @ 115200 baud            |
 |   - Mute PAM8302 Class-D (GPIO26 -> LOW)                |
 |   - Precompute default 40 kHz LUT                       |
 +----------------------------+----------------------------+
                              |
                              v
 +---------------------------------------------------------+
 |                      IDLE_STANDBY                       |
 |   - Low power listening mode                            |
 |   - Transducer amplifier muted (Zero acoustic emission) |
 |   - Waiting for AUV Command Packet                      |
 +----------------------------+----------------------------+
                              |
                              | [Command Packet Received & Validated]
                              v
 +---------------------------------------------------------+
 |                    COMMAND_RECEIVED                     |
 |   - Decode Mode, Freq, Sweep BW, Pulse Width, PRI       |
 |   - Recalculate DMA Waveform Buffer in background       |
 |   - Arm DMA Descriptor list                             |
 +----------------------------+----------------------------+
                              |
                              | [Trigger Ping Command or Periodic PRI Timer]
                              v
 +---------------------------------------------------------+
 |                    DRIVE_CLASS_D_AMP                    |
 |   - Enable PAM8302 Power Stage (GPIO26 -> HIGH)         |
 |   - Delay 100 us for Class-D oscillator stabilization   |
 |   - Start DMA Circular/One-Shot Transfer to DAC         |
 |   - Stream Windowed Waveform (Pulse Duration T)         |
 +----------------------------+----------------------------+
                              |
                              | [DMA Transfer Complete (t >= Pulse Width)]
                              v
 +---------------------------------------------------------+
 |                      DISABLE_AMP                        |
 |   - Stop DMA Stream / Reset DAC to mid-scale (DC 1.65V) |
 |   - Mute PAM8302 Power Stage (GPIO26 -> LOW)            |
 |   - Flush Transmit Buffers                              |
 +----------------------------+----------------------------+
                              |
                              v
                      [Return to IDLE_STANDBY]
```

## Acoustic Timing Constraints

| Parameter | Symbol | Nominal Value | Configurable Range |
| :--- | :--- | :--- | :--- |
| **Sampling Rate** | \(F_s\) | 500 kSPS | 200 kSPS – 1 MSPS |
| **Monofrequency CW** | \(f_0\) | 40 kHz | 20 kHz – 80 kHz |
| **LFM Chirp Start Freq** | \(f_{start}\) | 35 kHz | 20 kHz – 60 kHz |
| **LFM Chirp Stop Freq** | \(f_{stop}\) | 45 kHz | 25 kHz – 70 kHz |
| **Pulse Duration** | \(T\) | 5 ms | 0.5 ms – 50 ms |
| **Pulse Repetition Interval** | \(PRI\) | 200 ms (5 Hz) | 50 ms – 5000 ms |
| **Amp Pre-Warm Time** | \(t_{warm}\) | 100 \(\mu\text{s}\) | 50 \(\mu\text{s}\) – 500 \(\mu\text{s}\) |
| **Amp Ringdown Mute** | \(t_{mute}\) | 50 \(\mu\text{s}\) | 20 \(\mu\text{s}\) – 200 \(\mu\text{s}\) |
