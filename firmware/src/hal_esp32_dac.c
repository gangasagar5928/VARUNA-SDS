#include "hal_dac.h"
#include "config.h"
#include <stdio.h>

#if defined(ARDUINO) || defined(ESP32)
#include <Arduino.h>
#include "driver/dac.h"
#include "driver/i2s.h"
#include "esp_timer.h"
#include "rom/ets_sys.h"

static bool s_hal_initialized = false;

bool hal_dac_init(void) {
    pinMode(PIN_AMP_ENABLE, OUTPUT);
    digitalWrite(PIN_AMP_ENABLE, LOW); // Start with amplifier muted

    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, LOW);

    // Enable DAC channel 1 (GPIO25)
    dac_output_enable(DAC_CHANNEL_1);
    dac_output_voltage(DAC_CHANNEL_1, DDS_DAC_MIDSCALE);

    s_hal_initialized = true;
    return true;
}

void hal_amp_set_enable(bool enable) {
    digitalWrite(PIN_AMP_ENABLE, enable ? HIGH : LOW);
    digitalWrite(PIN_STATUS_LED, enable ? HIGH : LOW);
}

void hal_dac_set_idle(void) {
    dac_output_voltage(DAC_CHANNEL_1, DDS_DAC_MIDSCALE);
}

bool hal_dac_transmit_burst(const dds_waveform_t *wf) {
    if (!s_hal_initialized || !wf || wf->sample_count == 0) return false;

    // 1. Enable PAM8302 Class-D amplifier stage
    hal_amp_set_enable(true);
    ets_delay_us(100); // 100us pre-warm for Class-D oscillator stabilization

    // 2. High-speed timed DAC output burst
    // In tight loop with cycle-accurate timing (or DMA if I2S mapped)
    for (uint32_t i = 0; i < wf->sample_count; i++) {
        dac_output_voltage(DAC_CHANNEL_1, wf->buffer[i]);
        ets_delay_us(2); // 500 kSPS nominal timing interval
    }

    // 3. Reset DAC to idle midscale and shutdown Class-D stage
    hal_dac_set_idle();
    ets_delay_us(50); // Ringdown absorption
    hal_amp_set_enable(false);

    return true;
}

#else
// Desktop / Generic Simulation Fallback
static bool s_mock_amp_enabled = false;

bool hal_dac_init(void) {
    printf("[HAL] DAC & DMA initialized (Generic/Sim mode)\n");
    return true;
}

void hal_amp_set_enable(bool enable) {
    s_mock_amp_enabled = enable;
    printf("[HAL] PAM8302 Power Stage: %s\n", enable ? "ENABLED (DRIVING)" : "MUTED (STANDBY)");
}

void hal_dac_set_idle(void) {
    // Set midscale DC
}

bool hal_dac_transmit_burst(const dds_waveform_t *wf) {
    if (!wf) return false;
    hal_amp_set_enable(true);
    printf("[HAL] Transmitting %u samples (%u us pulse) via DAC Channel 1\n", 
           (unsigned int)wf->sample_count, (unsigned int)wf->duration_us);
    hal_dac_set_idle();
    hal_amp_set_enable(false);
    return true;
}
#endif
