#include "dds_engine.h"
#include <math.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define SINE_LUT_SIZE 1024
static float s_sine_lut[SINE_LUT_SIZE];
static bool s_initialized = false;

void dds_engine_init(void) {
    if (s_initialized) return;

    for (int i = 0; i < SINE_LUT_SIZE; i++) {
        float angle = (2.0f * (float)M_PI * (float)i) / (float)SINE_LUT_SIZE;
        s_sine_lut[i] = sinf(angle);
    }
    s_initialized = true;
}

static inline float get_lut_sample(uint32_t phase_acc_32) {
    // Top 10 bits index the 1024-entry lookup table
    uint32_t idx = (phase_acc_32 >> 22) & (SINE_LUT_SIZE - 1);
    return s_sine_lut[idx];
}

static float calculate_window(uint32_t n, uint32_t total_samples, window_type_t window) {
    if (total_samples <= 1) return 1.0f;
    float pos = (float)n / (float)(total_samples - 1);

    switch (window) {
        case WINDOW_HANN:
            return 0.5f * (1.0f - cosf(2.0f * (float)M_PI * pos));

        case WINDOW_TUKEY: {
            // Tukey window with r = 0.2 (10% rise, 80% flat, 10% fall)
            float r = 0.2f;
            if (pos < r / 2.0f) {
                return 0.5f * (1.0f + cosf((2.0f * (float)M_PI / r) * (pos - r / 2.0f)));
            } else if (pos <= 1.0f - r / 2.0f) {
                return 1.0f;
            } else {
                return 0.5f * (1.0f + cosf((2.0f * (float)M_PI / r) * (pos - 1.0f + r / 2.0f)));
            }
        }

        case WINDOW_RECTANGULAR:
        default:
            return 1.0f;
    }
}

int dds_synthesize_cw(dds_waveform_t *wf, 
                      uint32_t freq_hz, 
                      uint32_t duration_us, 
                      uint8_t amplitude, 
                      window_type_t window) {
    if (!wf) return -1;
    dds_engine_init();

    uint32_t num_samples = (uint32_t)(((uint64_t)duration_us * DDS_SAMPLE_RATE_HZ) / 1000000ULL);
    if (num_samples > DDS_MAX_BUFFER_SAMPLES) {
        num_samples = DDS_MAX_BUFFER_SAMPLES;
    }
    if (num_samples == 0) return -2;

    float max_amp = (float)(amplitude > DDS_DAC_AMPLITUDE ? DDS_DAC_AMPLITUDE : amplitude);

    // Fixed-Point 32-bit Phase Accumulator (Standard DDS Architecture)
    // Phase increment: delta_phase = (freq * 2^32) / Fs
    uint32_t phase_acc = 0;
    uint32_t phase_inc = (uint32_t)(((uint64_t)freq_hz << 32) / (uint64_t)DDS_SAMPLE_RATE_HZ);

    for (uint32_t n = 0; n < num_samples; n++) {
        float raw_sine = get_lut_sample(phase_acc);
        phase_acc += phase_inc; // Natural 32-bit integer overflow provides exact 2pi wrapping with zero drift

        float win = calculate_window(n, num_samples, window);
        float sample_val = (max_amp * raw_sine * win) + (float)DDS_DAC_MIDSCALE;

        // Clamp to 8-bit DAC range [0, 255]
        if (sample_val < 0.0f) sample_val = 0.0f;
        if (sample_val > 255.0f) sample_val = 255.0f;

        wf->buffer[n] = (uint8_t)(sample_val + 0.5f);
    }

    wf->sample_count = num_samples;
    wf->duration_us = duration_us;
    wf->mode = SONAR_MODE_CW_PING;
    return 0;
}

int dds_synthesize_chirp(dds_waveform_t *wf, 
                         uint32_t start_freq_hz, 
                         uint32_t stop_freq_hz, 
                         uint32_t duration_us, 
                         uint8_t amplitude, 
                         window_type_t window) {
    if (!wf) return -1;
    dds_engine_init();

    uint32_t num_samples = (uint32_t)(((uint64_t)duration_us * DDS_SAMPLE_RATE_HZ) / 1000000ULL);
    if (num_samples > DDS_MAX_BUFFER_SAMPLES) {
        num_samples = DDS_MAX_BUFFER_SAMPLES;
    }
    if (num_samples == 0) return -2;

    float max_amp = (float)(amplitude > DDS_DAC_AMPLITUDE ? DDS_DAC_AMPLITUDE : amplitude);

    // Double-Accumulator Direct Digital Chirp Synthesis (DDCS)
    // Instantaneous frequency sweeps linearly from start_freq_hz to stop_freq_hz:
    // f(n) = f_start + ((f_stop - f_start) * n) / num_samples
    // phase_inc(n) = (f(n) * 2^32) / Fs
    // Uses 64-bit fixed-point for chirp rate accumulator to eliminate floating-point phase truncation
    uint32_t phase_acc = 0;
    uint64_t phase_inc_64 = ((uint64_t)start_freq_hz << 32) / (uint64_t)DDS_SAMPLE_RATE_HZ;
    int64_t chirp_rate_delta_64 = 0;

    if (num_samples > 1) {
        int64_t total_freq_span = (int64_t)stop_freq_hz - (int64_t)start_freq_hz;
        chirp_rate_delta_64 = ((total_freq_span << 32) / (int64_t)num_samples) / (int64_t)DDS_SAMPLE_RATE_HZ;
    }

    for (uint32_t n = 0; n < num_samples; n++) {
        float raw_sine = get_lut_sample(phase_acc);

        // Update phase accumulator and instantaneous phase increment
        phase_acc += (uint32_t)phase_inc_64;
        phase_inc_64 += chirp_rate_delta_64;

        float win = calculate_window(n, num_samples, window);
        float sample_val = (max_amp * raw_sine * win) + (float)DDS_DAC_MIDSCALE;

        // Clamp to 8-bit DAC range [0, 255]
        if (sample_val < 0.0f) sample_val = 0.0f;
        if (sample_val > 255.0f) sample_val = 255.0f;

        wf->buffer[n] = (uint8_t)(sample_val + 0.5f);
    }

    wf->sample_count = num_samples;
    wf->duration_us = duration_us;
    wf->mode = SONAR_MODE_LFM_CHIRP;
    return 0;
}

int dds_generate_from_config(dds_waveform_t *wf, const sonar_config_t *cfg) {
    if (!wf || !cfg) return -1;

    if (cfg->mode == SONAR_MODE_CW_PING) {
        return dds_synthesize_cw(wf, 
                                 cfg->center_freq_hz, 
                                 cfg->pulse_duration_us, 
                                 cfg->amplitude, 
                                 cfg->window_type);
    } else if (cfg->mode == SONAR_MODE_LFM_CHIRP) {
        return dds_synthesize_chirp(wf, 
                                    cfg->chirp_start_freq_hz, 
                                    cfg->chirp_stop_freq_hz, 
                                    cfg->pulse_duration_us, 
                                    cfg->amplitude, 
                                    cfg->window_type);
    } else {
        // Standby mode: flat midscale DC bias
        memset(wf->buffer, DDS_DAC_MIDSCALE, DDS_MAX_BUFFER_SAMPLES);
        wf->sample_count = 64;
        wf->duration_us = 100;
        wf->mode = SONAR_MODE_STANDBY;
        return 0;
    }
}
