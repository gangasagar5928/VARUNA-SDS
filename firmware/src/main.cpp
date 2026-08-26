#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>

#include "config.h"
#include "dds_engine.h"
#include "sonar_protocol.h"
#include "hal_dac.h"

#ifdef ARDUINO
#include <Arduino.h>
#endif

typedef enum {
    STATE_POWER_ON,
    STATE_SYSTEM_INIT,
    STATE_IDLE_STANDBY,
    STATE_COMMAND_RECEIVED,
    STATE_DRIVE_CLASS_D_AMP,
    STATE_DISABLE_AMP
} system_state_t;

static system_state_t s_current_state = STATE_POWER_ON;
static sonar_config_t s_config;
static dds_waveform_t s_active_waveform;
static uint32_t s_last_ping_time_ms = 0;
static bool s_trigger_pending = false;

void setup_system(void) {
    s_current_state = STATE_SYSTEM_INIT;
    printf("\r\n==============================================\r\n");
    printf("VARUNA-SDS: Software-Defined Sonar Payload\r\n");
    printf("Adaptive Subsea Acoustic Waveform Synthesis\r\n");
    printf("==============================================\r\n");

    // 1. Initialize DDS look-up table engine
    dds_engine_init();

    // 2. Initialize Hardware DAC / DMA & amplifier mute line
    hal_dac_init();
    hal_amp_set_enable(false);

    // 3. Load default sonar configuration
    sonar_protocol_init(&s_config);

    // 4. Precompute initial waveform (Mode A: 40 kHz Monofrequency)
    dds_generate_from_config(&s_active_waveform, &s_config);

    printf("[STATE] SYSTEM_INIT Complete. Entering IDLE_STANDBY.\r\n");
    s_current_state = STATE_IDLE_STANDBY;
}

void process_sonar_fsm(void) {
    switch (s_current_state) {
        case STATE_IDLE_STANDBY: {
            // Check auto-trigger timer if enabled
#ifdef ARDUINO
            uint32_t now = millis();
#else
            static uint32_t now = 0;
            now += 50;
#endif
            if (s_config.auto_trigger && (now - s_last_ping_time_ms >= s_config.pri_ms)) {
                s_last_ping_time_ms = now;
                s_trigger_pending = true;
            }

            if (s_trigger_pending) {
                s_trigger_pending = false;
                s_current_state = STATE_DRIVE_CLASS_D_AMP;
            }
            break;
        }

        case STATE_COMMAND_RECEIVED: {
            // Regenerate waveform buffer based on updated protocol params
            printf("[FSM] Updating DDS Waveform Buffer...\r\n");
            dds_generate_from_config(&s_active_waveform, &s_config);
            printf("[FSM] DDS Buffer Ready: %u samples (%u us)\r\n", 
                   (unsigned int)s_active_waveform.sample_count, 
                   (unsigned int)s_active_waveform.duration_us);
            s_current_state = STATE_IDLE_STANDBY;
            break;
        }

        case STATE_DRIVE_CLASS_D_AMP: {
            printf("[FSM] PING BURST: Transmitting %s...\r\n", 
                   s_config.mode == SONAR_MODE_CW_PING ? "40kHz CW Ping" : "35-45kHz LFM Chirp");
            hal_dac_transmit_burst(&s_active_waveform);
            s_current_state = STATE_DISABLE_AMP;
            break;
        }

        case STATE_DISABLE_AMP: {
            hal_amp_set_enable(false);
            hal_dac_set_idle();
            s_current_state = STATE_IDLE_STANDBY;
            break;
        }

        default:
            s_current_state = STATE_IDLE_STANDBY;
            break;
    }
}

#ifdef ARDUINO
void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 1000);
    setup_system();
}

void loop() {
    // Read incoming UART commands
    while (Serial.available()) {
        char c = (char)Serial.read();
        cmd_result_t res = sonar_protocol_process_byte(c, &s_config);
        if (res == CMD_RESULT_CONFIG_UPDATED) {
            s_current_state = STATE_COMMAND_RECEIVED;
        } else if (res == CMD_RESULT_PING_TRIGGERED) {
            s_trigger_pending = true;
        }
    }

    process_sonar_fsm();
}

#else
// Standard C/C++ Main for Desktop verification & CLI simulation
int main(int argc, char **argv) {
    setup_system();

    printf("\r\nSimulating AUV Command Sequence:\r\n");

    // 1. Trigger default 40 kHz Ping
    printf("\r\n--- Step 1: Triggering default CW Ping ---\r\n");
    sonar_protocol_parse_line("PING", &s_config);
    s_trigger_pending = true;
    process_sonar_fsm();

    // 2. Switch to Mode B: LFM Chirp 35 kHz -> 45 kHz
    printf("\r\n--- Step 2: Reconfiguring to Mode B (LFM Chirp 35kHz -> 45kHz) ---\r\n");
    sonar_protocol_parse_line("SET_CHIRP 35000 45000", &s_config);
    sonar_protocol_parse_line("SET_DURATION 8000", &s_config); // 8 ms
    sonar_protocol_parse_line("SET_WINDOW 2", &s_config);      // Tukey
    s_current_state = STATE_COMMAND_RECEIVED;
    process_sonar_fsm();

    // 3. Trigger Chirp Ping
    printf("\r\n--- Step 3: Triggering LFM Chirp Ping ---\r\n");
    sonar_protocol_parse_line("PING", &s_config);
    s_trigger_pending = true;
    process_sonar_fsm();

    // 4. Query status
    printf("\r\n--- Step 4: Querying System Configuration ---\r\n");
    sonar_protocol_parse_line("GET_CONFIG", &s_config);

    printf("\r\nSimulation Run Complete.\r\n");
    return 0;
}
#endif
