#include "hal_dac.h"
#include "config.h"
#include <stdio.h>
#include <string.h>

#if defined(ARDUINO) || defined(ESP32)
#include <Arduino.h>
#include "driver/dac.h"
#include "driver/i2s.h"
#include "esp_timer.h"
#include "rom/ets_sys.h"

#define I2S_PORT_NUM       I2S_NUM_0
#define DMA_BUFFER_COUNT   2
#define DMA_BUFFER_LEN     512

static bool s_hal_initialized = false;
static uint16_t s_dma_tx_buf[DDS_MAX_BUFFER_SAMPLES * 2]; // 16-bit stereo frame buffer for I2S DAC

bool hal_dac_init(void) {
    pinMode(PIN_AMP_ENABLE, OUTPUT);
    digitalWrite(PIN_AMP_ENABLE, LOW); // Start with amplifier muted

    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, LOW);

    // Configure I2S in built-in DAC mode with hardware DMA
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX | I2S_MODE_DAC_BUILT_IN),
        .sample_rate = DDS_SAMPLE_RATE_HZ,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_MSB,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = DMA_BUFFER_COUNT,
        .dma_buf_len = DMA_BUFFER_LEN,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = 0
    };

    esp_err_t err = i2s_driver_install(I2S_PORT_NUM, &i2s_config, 0, NULL);
    if (err != ESP_OK) {
        // Fallback: direct DAC channel enable if I2S fails
        dac_output_enable(DAC_CHANNEL_1);
        dac_output_voltage(DAC_CHANNEL_1, DDS_DAC_MIDSCALE);
        s_hal_initialized = true;
        return false;
    }

    // Enable internal DAC channel (GPIO25 = DAC_CHANNEL_1 / I2S_DAC_CHANNEL_RIGHT_EN)
    i2s_set_dac_mode(I2S_DAC_CHANNEL_RIGHT_EN);
    i2s_set_sample_rates(I2S_PORT_NUM, DDS_SAMPLE_RATE_HZ);

    s_hal_initialized = true;
    return true;
}

void hal_amp_set_enable(bool enable) {
    digitalWrite(PIN_AMP_ENABLE, enable ? HIGH : LOW);
    digitalWrite(PIN_STATUS_LED, enable ? HIGH : LOW);
}

void hal_dac_set_idle(void) {
    // Send zero/midscale frames to DMA or direct DAC
    uint16_t idle_sample = ((uint16_t)DDS_DAC_MIDSCALE) << 8;
    for (int i = 0; i < 64; i++) {
        s_dma_tx_buf[i * 2] = idle_sample;
        s_dma_tx_buf[i * 2 + 1] = idle_sample;
    }
    size_t bytes_written = 0;
    i2s_write(I2S_PORT_NUM, s_dma_tx_buf, 64 * 4, &bytes_written, 10 / portTICK_PERIOD_MS);
}

bool hal_dac_transmit_burst(const dds_waveform_t *wf) {
    if (!s_hal_initialized || !wf || wf->sample_count == 0) return false;

    // 1. Enable PAM8302 Class-D amplifier stage
    hal_amp_set_enable(true);
    ets_delay_us(100); // 100 us pre-warm for Class-D oscillator stabilization

    // 2. Prepare 16-bit DMA stereo frames (upper byte holds 8-bit DAC voltage)
    uint32_t count = wf->sample_count;
    if (count > DDS_MAX_BUFFER_SAMPLES) count = DDS_MAX_BUFFER_SAMPLES;

    for (uint32_t i = 0; i < count; i++) {
        uint16_t dac_val16 = ((uint16_t)wf->buffer[i]) << 8;
        s_dma_tx_buf[i * 2]     = dac_val16; // Left channel
        s_dma_tx_buf[i * 2 + 1] = dac_val16; // Right channel (GPIO25 DAC)
    }

    // 3. True Non-blocking DMA Transfer via I2S hardware FIFO
    size_t bytes_to_write = count * 4; // 2 channels * 2 bytes/sample
    size_t bytes_written = 0;
    i2s_write(I2S_PORT_NUM, s_dma_tx_buf, bytes_to_write, &bytes_written, portMAX_DELAY);

    // 4. Reset DAC to idle midscale and shutdown Class-D stage
    ets_delay_us(50); // Ringdown absorption
    hal_dac_set_idle();
    hal_amp_set_enable(false);

    return true;
}

#else
// Desktop / Generic Simulation Fallback
static bool s_mock_amp_enabled = false;

bool hal_dac_init(void) {
    printf("[HAL] DAC & DMA controller initialized (Simulation/Desktop Mode)\n");
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
    printf("[HAL-DMA] Hardware DMA Transfer: %u samples (%u us pulse) streamed to DAC1\n", 
           (unsigned int)wf->sample_count, (unsigned int)wf->duration_us);
    hal_dac_set_idle();
    hal_amp_set_enable(false);
    return true;
}
#endif
