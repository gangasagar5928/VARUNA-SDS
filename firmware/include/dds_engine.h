#pragma once

#include "config.h"
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Waveform buffer container
typedef struct {
    uint8_t buffer[DDS_MAX_BUFFER_SAMPLES];
    uint32_t sample_count;
    uint32_t duration_us;
    sonar_mode_t mode;
} dds_waveform_t;

/**
 * @brief Initialize DDS lookup tables and internal math constants
 */
void dds_engine_init(void);

/**
 * @brief Synthesize a Monofrequency CW Ping waveform into destination buffer
 * 
 * @param wf Pointer to output waveform structure
 * @param freq_hz Frequency in Hertz (e.g., 40000)
 * @param duration_us Pulse duration in microseconds
 * @param amplitude Peak amplitude (1 - 127)
 * @param window Windowing function to apply
 * @return int 0 on success, negative error code on buffer overflow
 */
int dds_synthesize_cw(dds_waveform_t *wf, 
                      uint32_t freq_hz, 
                      uint32_t duration_us, 
                      uint8_t amplitude, 
                      window_type_t window);

/**
 * @brief Synthesize an LFM (Linear Frequency Modulation) Chirp waveform
 * 
 * Frequency sweeps linearly from start_freq_hz to stop_freq_hz over duration_us.
 * 
 * @param wf Pointer to output waveform structure
 * @param start_freq_hz Start frequency in Hertz (e.g., 35000)
 * @param stop_freq_hz Stop frequency in Hertz (e.g., 45000)
 * @param duration_us Pulse duration in microseconds
 * @param amplitude Peak amplitude (1 - 127)
 * @param window Windowing function to apply
 * @return int 0 on success, negative error code on buffer overflow
 */
int dds_synthesize_chirp(dds_waveform_t *wf, 
                         uint32_t start_freq_hz, 
                         uint32_t stop_freq_hz, 
                         uint32_t duration_us, 
                         uint8_t amplitude, 
                         window_type_t window);

/**
 * @brief Generate waveform from active configuration struct
 */
int dds_generate_from_config(dds_waveform_t *wf, const sonar_config_t *cfg);

#ifdef __cplusplus
}
#endif
