#pragma once

#include "config.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    CMD_RESULT_OK = 0,
    CMD_RESULT_PING_TRIGGERED,
    CMD_RESULT_CONFIG_UPDATED,
    CMD_RESULT_ERROR_SYNTAX,
    CMD_RESULT_ERROR_PARAM_OUT_OF_RANGE,
    CMD_RESULT_NONE
} cmd_result_t;

/**
 * @brief Initialize protocol state and load default configs
 */
void sonar_protocol_init(sonar_config_t *cfg);

/**
 * @brief Process incoming UART bytes and parse CLI commands
 * 
 * @param byte Incoming character
 * @param cfg Active sonar configuration to modify
 * @return cmd_result_t Status of command processing
 */
cmd_result_t sonar_protocol_process_byte(char byte, sonar_config_t *cfg);

/**
 * @brief Parse a complete null-terminated command string
 */
cmd_result_t sonar_protocol_parse_line(const char *cmd_line, sonar_config_t *cfg);

#ifdef __cplusplus
}
#endif
