#pragma once

#include "dds_engine.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize Hardware DAC and DMA controller
 */
bool hal_dac_init(void);

/**
 * @brief Transmit a single waveform burst via DMA to DAC
 * 
 * Drives PAM8302 enable pin HIGH, streams DMA buffer, then disables PAM8302.
 * 
 * @param wf Waveform data to transmit
 * @return bool true if transfer triggered successfully
 */
bool hal_dac_transmit_burst(const dds_waveform_t *wf);

/**
 * @brief Enable or disable PAM8302 Power Amplifier stage
 */
void hal_amp_set_enable(bool enable);

/**
 * @brief Set DAC output to idle DC bias (midscale 1.65V)
 */
void hal_dac_set_idle(void);

#ifdef __cplusplus
}
#endif
