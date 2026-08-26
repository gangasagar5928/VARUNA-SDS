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
#define PIN_AMP_ENABLE       26   // PAM8302 Shutdown/Mute (Active LOW for shutdown, HIGH to enable)
#define PIN_UART_RX          16   // Telemetry RX2
#define PIN_UART_TX          17   // Telemetry TX2
#define PIN_STATUS_LED       2    // Status / Ping indicator LED

// ============================================================================
// DDS & DAC SAMPLING PARAMETERS
// ============================================================================
#define DDS_SAMPLE_RATE_HZ   500000UL  // 500 kSPS sampling rate
#define DDS_MAX_BUFFER_SAMPLES 4096    // Max samples per pulse buffer
#define DDS_DAC_MIDSCALE     128       // 8-bit DAC DC offset (2.5V/1.65V center)
#define DDS_DAC_AMPLITUDE    120       // Max peak amplitude (prevents DAC saturation clipping)

// ============================================================================
// SONAR MODES & DEFAULT TIMINGS
// ============================================================================
typedef enum {
    SONAR_MODE_CW_PING = 0,    // Mode A: Monofrequency CW Ping (40 kHz)
    SONAR_MODE_LFM_CHIRP = 1,  // Mode B: Linear Frequency Modulation (35 - 45 kHz)
    SONAR_MODE_STANDBY = 2     // Muted idle state
} sonar_mode_t;

typedef enum {
    WINDOW_RECTANGULAR = 0,
    WINDOW_HANN = 1,
    WINDOW_TUKEY = 2          // Flat top with cosine tapered edges (optimal for transducers)
} window_type_t;

typedef struct {
    sonar_mode_t mode;
    uint32_t center_freq_hz;     // Default: 40000 Hz
    uint32_t chirp_start_freq_hz;// Default: 35000 Hz
    uint32_t chirp_stop_freq_hz; // Default: 45000 Hz
    uint32_t pulse_duration_us;  // Default: 5000 us (5 ms)
    uint32_t pri_ms;             // Pulse Repetition Interval (Default: 200 ms -> 5 pings/sec)
    uint8_t  amplitude;          // Output amplitude 0-127
    window_type_t window_type;   // Windowing method
    bool auto_trigger;           // Auto repeat at PRI or wait for explicit manual triggers
} sonar_config_t;

#ifdef __cplusplus
}
#endif
