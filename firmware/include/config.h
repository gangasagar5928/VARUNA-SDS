#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// HARDWARE PIN DEFINITIONS
// ============================================================================
#define PIN_DAC_OUT          25   // ESP32 DAC Channel 1 (GPIO25)
#define PIN_AMP_ENABLE       26   // PAM8302 Shutdown/Mute (Active LOW = shutdown, HIGH = enable)
#define PIN_UART_RX          16   // Telemetry RX2
#define PIN_UART_TX          17   // Telemetry TX2
#define PIN_STATUS_LED       2    // Status / Ping indicator LED

// ============================================================================
// DDS & DAC SAMPLING PARAMETERS
// ============================================================================
#define DDS_SAMPLE_RATE_HZ   500000UL  // 500 kSPS nominal (ESP32 internal DAC via tight loop)
#define DDS_MAX_BUFFER_SAMPLES 4096    // Max samples per pulse buffer
#define DDS_DAC_MIDSCALE     128       // 8-bit DAC DC offset (center = 1.65V on 3.3V rail)
#define DDS_DAC_AMPLITUDE    120       // Peak amplitude (prevents DAC clipping)

/*
 * PROTOTYPE DESIGN NOTE — DDS Fidelity:
 * ----------------------------------------
 * At 500 kSPS and 40 kHz carrier:
 *   samples_per_cycle = 500,000 / 40,000 = 12.5
 *
 * 12.5 samples/cycle is prototype-grade.
 * Estimated SFDR (Spurious-Free Dynamic Range) for 8-bit DAC at 12.5 samp/cycle ≈ -40 dBc.
 * This is acceptable for a hackathon transmitter but NOT for precision ranging.
 *
 * Production upgrade path:
 *   - Use external 16-bit 1 MSPS DAC (e.g., DAC8830, AD9767)  → 25 samp/cycle → ~-80 dBc SFDR
 *   - Or use Xilinx Zynq-7000 / Spartan-7 FPGA at 10 MSPS     → 250 samp/cycle → full 16-bit fidelity
 *
 * PROTOTYPE DRIVER NOTE — PAM8302 Amplifier:
 * -------------------------------------------
 * PAM8302 is rated for audio: 20 Hz – 20 kHz. Driving at 40 kHz (ultrasonic) is
 * outside its datasheet specification. Output power drops sharply above 20 kHz.
 * For this prototype it functions as a current booster for the piezo load at reduced power.
 *
 * Production upgrade: Dedicated ultrasonic driver IC, e.g.:
 *   - TC1427 Dual MOSFET Driver (up to 200 kHz, complementary output, ±1.5A peak)
 *   - L298N half-bridge or custom Class-D H-bridge at 40–200 kHz
 *
 * LC RECONSTRUCTION FILTER (CORRECTED):
 * -------------------------------------------
 * Component values: L = 68 µH, C = 150 nF (single-ended per output leg)
 * Cutoff: fc = 1 / (2π√(68e-6 × 150e-9)) ≈ 49.8 kHz
 *
 * WHY: fc MUST be ABOVE the 40 kHz sonar carrier. An earlier design used
 * 100 µH + 100 nF which gave fc ≈ 35.59 kHz — BELOW the carrier, attenuating the
 * sonar signal itself. This is a critical error corrected in v1.1.
 *
 * At fc = 49.8 kHz:
 *   - 40 kHz sonar signal: +6.1 dB (near-resonance peaking, signal fully passes)
 *   - 250 kHz PAM8302 switching: -27.7 dB (carrier suppressed)
 *   - Net suppression margin: 33.8 dB
 */

// ============================================================================
// SONAR MODES & DEFAULT TIMINGS
// ============================================================================
typedef enum {
    SONAR_MODE_CW_PING = 0,    // Mode A: Monofrequency CW Ping (40 kHz)
    SONAR_MODE_LFM_CHIRP = 1,  // Mode B: Linear Frequency Modulation (35–45 kHz)
    SONAR_MODE_STANDBY = 2     // Muted idle state
} sonar_mode_t;

typedef enum {
    WINDOW_RECTANGULAR = 0,
    WINDOW_HANN = 1,
    WINDOW_TUKEY = 2          // Flat-top with cosine-tapered edges (optimal for transducers)
} window_type_t;

typedef struct {
    sonar_mode_t mode;
    uint32_t center_freq_hz;      // Default: 40000 Hz
    uint32_t chirp_start_freq_hz; // Default: 35000 Hz
    uint32_t chirp_stop_freq_hz;  // Default: 45000 Hz
    uint32_t pulse_duration_us;   // Default: 5000 us (5 ms)
    uint32_t pri_ms;              // Pulse Repetition Interval (Default: 200 ms = 5 pings/sec)
    uint8_t  amplitude;           // Output amplitude 0–127
    window_type_t window_type;    // Windowing method
    bool auto_trigger;            // Auto repeat at PRI or wait for explicit trigger
} sonar_config_t;

// ============================================================================
// KNOWN DESIGN GAPS (v1.0 Prototype)
// ============================================================================
/*
 * 1. TRANSMIT-ONLY SYSTEM: No receive (Rx) path is implemented. Echo reception,
 *    hydrophone preamp, ADC digitization, and time-of-flight extraction are
 *    deferred to v2.0. This is a sonar transmitter payload, not a full transceiver.
 *
 * 2. TRANSDUCER IMPEDANCE: The JSN-SR04T piezo disc is a consumer-grade component.
 *    Its impedance at 40 kHz in water is uncharacterized. In production, a
 *    calibrated PZT-5H Tonpilz with a known impedance model (e.g., KLM model) would
 *    be used, and an impedance matching network would be tuned accordingly.
 *
 * 3. DEPTH RATING: The 100 m IP68 depth claim applies to the target production
 *    pressure hull (6061 anodized aluminium vessel). The hackathon prototype uses
 *    an acrylic enclosure rated only for shallow tank testing (<0.5 m depth).
 *    No hydrostatic pressure simulation has been performed.
 */

#ifdef __cplusplus
}
#endif
