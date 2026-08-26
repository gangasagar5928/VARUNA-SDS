#include "sonar_protocol.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include <errno.h>

#define RX_BUFFER_SIZE 128
static char s_rx_buf[RX_BUFFER_SIZE];
static uint8_t s_rx_idx = 0;

void sonar_protocol_init(sonar_config_t *cfg) {
    if (!cfg) return;
    cfg->mode = SONAR_MODE_CW_PING;
    cfg->center_freq_hz = 40000;
    cfg->chirp_start_freq_hz = 35000;
    cfg->chirp_stop_freq_hz = 45000;
    cfg->pulse_duration_us = 5000; // 5 ms
    cfg->pri_ms = 200;             // 5 pings/sec
    cfg->amplitude = 120;
    cfg->window_type = WINDOW_TUKEY;
    cfg->auto_trigger = false;

    s_rx_idx = 0;
    memset(s_rx_buf, 0, RX_BUFFER_SIZE);
}

static void trim_whitespace(char *str) {
    if (!str || *str == '\0') return;

    // Advance past leading whitespace
    char *start = str;
    while (*start && isspace((unsigned char)*start)) {
        start++;
    }
    if (*start == '\0') {
        *str = '\0';
        return;
    }

    // Trim trailing whitespace
    char *end = start + strlen(start) - 1;
    while (end > start && isspace((unsigned char)*end)) {
        end--;
    }
    *(end + 1) = '\0';

    // Shift trimmed string to beginning of buffer
    if (start > str) {
        memmove(str, start, strlen(start) + 1);
    }
}

cmd_result_t sonar_protocol_parse_line(const char *cmd_line, sonar_config_t *cfg) {
    if (!cmd_line || !cfg) return CMD_RESULT_ERROR_SYNTAX;

    char line[RX_BUFFER_SIZE];
    strncpy(line, cmd_line, sizeof(line) - 1);
    line[sizeof(line) - 1] = '\0';
    trim_whitespace(line);

    if (strlen(line) == 0) return CMD_RESULT_NONE;

    if (strcasecmp(line, "PING") == 0 || strcasecmp(line, "TRIG") == 0) {
        return CMD_RESULT_PING_TRIGGERED;
    }

    if (strncasecmp(line, "SET_MODE ", 9) == 0) {
        char *endptr = NULL;
        long m = strtol(line + 9, &endptr, 10);
        if (endptr == line + 9 || (*endptr != '\0' && !isspace((unsigned char)*endptr))) {
            return CMD_RESULT_ERROR_SYNTAX;
        }
        if (m >= 0 && m <= 2) {
            cfg->mode = (sonar_mode_t)m;
            return CMD_RESULT_CONFIG_UPDATED;
        }
        return CMD_RESULT_ERROR_PARAM_OUT_OF_RANGE;
    }

    if (strncasecmp(line, "SET_CW_FREQ ", 12) == 0) {
        char *endptr = NULL;
        unsigned long freq = strtoul(line + 12, &endptr, 10);
        if (endptr == line + 12 || (*endptr != '\0' && !isspace((unsigned char)*endptr))) {
            return CMD_RESULT_ERROR_SYNTAX;
        }
        if (freq >= 10000 && freq <= 100000) {
            cfg->center_freq_hz = (uint32_t)freq;
            cfg->mode = SONAR_MODE_CW_PING;
            return CMD_RESULT_CONFIG_UPDATED;
        }
        return CMD_RESULT_ERROR_PARAM_OUT_OF_RANGE;
    }

    if (strncasecmp(line, "SET_CHIRP ", 10) == 0) {
        unsigned long f_start = 0, f_stop = 0;
        char *ptr = line + 10;
        char *endptr1 = NULL;
        f_start = strtoul(ptr, &endptr1, 10);
        if (endptr1 == ptr) return CMD_RESULT_ERROR_SYNTAX;

        char *endptr2 = NULL;
        f_stop = strtoul(endptr1, &endptr2, 10);
        if (endptr2 == endptr1) return CMD_RESULT_ERROR_SYNTAX;

        if (f_start >= 10000 && f_stop <= 100000 && f_stop > f_start) {
            cfg->chirp_start_freq_hz = (uint32_t)f_start;
            cfg->chirp_stop_freq_hz = (uint32_t)f_stop;
            cfg->mode = SONAR_MODE_LFM_CHIRP;
            return CMD_RESULT_CONFIG_UPDATED;
        }
        return CMD_RESULT_ERROR_PARAM_OUT_OF_RANGE;
    }

    if (strncasecmp(line, "SET_DURATION ", 13) == 0) {
        char *endptr = NULL;
        unsigned long dur = strtoul(line + 13, &endptr, 10);
        if (endptr == line + 13 || (*endptr != '\0' && !isspace((unsigned char)*endptr))) {
            return CMD_RESULT_ERROR_SYNTAX;
        }
        if (dur >= 100 && dur <= 50000) { // 100 us to 50 ms
            cfg->pulse_duration_us = (uint32_t)dur;
            return CMD_RESULT_CONFIG_UPDATED;
        }
        return CMD_RESULT_ERROR_PARAM_OUT_OF_RANGE;
    }

    if (strncasecmp(line, "SET_PRI ", 8) == 0) {
        char *endptr = NULL;
        unsigned long pri = strtoul(line + 8, &endptr, 10);
        if (endptr == line + 8 || (*endptr != '\0' && !isspace((unsigned char)*endptr))) {
            return CMD_RESULT_ERROR_SYNTAX;
        }
        if (pri >= 10 && pri <= 10000) { // 10 ms to 10s
            cfg->pri_ms = (uint32_t)pri;
            return CMD_RESULT_CONFIG_UPDATED;
        }
        return CMD_RESULT_ERROR_PARAM_OUT_OF_RANGE;
    }

    if (strncasecmp(line, "SET_WINDOW ", 11) == 0) {
        char *endptr = NULL;
        long w = strtol(line + 11, &endptr, 10);
        if (endptr == line + 11 || (*endptr != '\0' && !isspace((unsigned char)*endptr))) {
            return CMD_RESULT_ERROR_SYNTAX;
        }
        if (w >= 0 && w <= 2) {
            cfg->window_type = (window_type_t)w;
            return CMD_RESULT_CONFIG_UPDATED;
        }
        return CMD_RESULT_ERROR_PARAM_OUT_OF_RANGE;
    }

    if (strncasecmp(line, "SET_AUTO ", 9) == 0) {
        char *endptr = NULL;
        long a = strtol(line + 9, &endptr, 10);
        if (endptr == line + 9 || (*endptr != '\0' && !isspace((unsigned char)*endptr))) {
            return CMD_RESULT_ERROR_SYNTAX;
        }
        cfg->auto_trigger = (a != 0);
        return CMD_RESULT_CONFIG_UPDATED;
    }

    if (strcasecmp(line, "GET_CONFIG") == 0 || strcasecmp(line, "STATUS") == 0) {
        printf("--- VARUNA-SDS CONFIG ---\r\n");
        printf("Mode: %s\r\n", cfg->mode == SONAR_MODE_CW_PING ? "CW Ping (Mode A)" : 
                              (cfg->mode == SONAR_MODE_LFM_CHIRP ? "LFM Chirp (Mode B)" : "STANDBY"));
        printf("CW Freq: %u Hz\r\n", (unsigned int)cfg->center_freq_hz);
        printf("Chirp: %u Hz -> %u Hz (BW = %u Hz)\r\n", 
               (unsigned int)cfg->chirp_start_freq_hz, 
               (unsigned int)cfg->chirp_stop_freq_hz, 
               (unsigned int)(cfg->chirp_stop_freq_hz - cfg->chirp_start_freq_hz));
        printf("Pulse Duration: %u us\r\n", (unsigned int)cfg->pulse_duration_us);
        printf("PRI: %u ms (Freq: %.2f Hz)\r\n", (unsigned int)cfg->pri_ms, 1000.0f / (float)cfg->pri_ms);
        printf("Window: %s\r\n", cfg->window_type == WINDOW_RECTANGULAR ? "Rectangular" : 
                                (cfg->window_type == WINDOW_HANN ? "Hann" : "Tukey"));
        printf("Auto-Trigger: %s\r\n", cfg->auto_trigger ? "ENABLED" : "DISABLED");
        printf("------------------------\r\n");
        return CMD_RESULT_OK;
    }

    if (strcasecmp(line, "HELP") == 0 || strcasecmp(line, "?") == 0) {
        printf("--- VARUNA-SDS COMMAND HELP ---\r\n");
        printf("PING                       : Trigger single sonar pulse\r\n");
        printf("SET_MODE <0|1|2>           : 0=CW, 1=LFM Chirp, 2=Standby\r\n");
        printf("SET_CW_FREQ <Hz>           : Set Monofrequency (e.g. 40000)\r\n");
        printf("SET_CHIRP <start> <stop>   : Set LFM sweep (e.g. 35000 45000)\r\n");
        printf("SET_DURATION <us>          : Set pulse width in microseconds\r\n");
        printf("SET_PRI <ms>               : Set repetition interval (ms)\r\n");
        printf("SET_WINDOW <0|1|2>         : 0=Rect, 1=Hann, 2=Tukey\r\n");
        printf("SET_AUTO <0|1>             : 1=Auto-ping at PRI, 0=Manual\r\n");
        printf("GET_CONFIG                 : Print current settings\r\n");
        printf("-------------------------------\r\n");
        return CMD_RESULT_OK;
    }

    return CMD_RESULT_ERROR_SYNTAX;
}

cmd_result_t sonar_protocol_process_byte(char byte, sonar_config_t *cfg) {
    if (byte == '\r' || byte == '\n') {
        if (s_rx_idx > 0) {
            s_rx_buf[s_rx_idx] = '\0';
            cmd_result_t res = sonar_protocol_parse_line(s_rx_buf, cfg);
            s_rx_idx = 0;
            return res;
        }
        return CMD_RESULT_NONE;
    }

    if (s_rx_idx < (RX_BUFFER_SIZE - 1)) {
        s_rx_buf[s_rx_idx++] = byte;
    } else {
        // Overflow protection: clear buffer
        s_rx_idx = 0;
    }
    return CMD_RESULT_NONE;
}
