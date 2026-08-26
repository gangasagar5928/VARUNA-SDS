"""
VARUNA-SDS: Waveform & DSP Visualizer
Generates publication-quality acoustic waveforms, spectrograms, matched filter envelopes, and Bode plots.
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from dds_synthesizer import DDSSynthesizer
from acoustic_channel import UnderwaterAcousticChannel
from matched_filter import MatchedFilterReceiver
from lc_filter_sim import LCReconstructionFilter


def generate_all_plots(output_file: str = "assets/simulation_plots.png"):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[Error] matplotlib is required for plotting. Install via 'pip install matplotlib'.")
        return

    fs = 500_000
    dds = DDSSynthesizer(sample_rate_hz=fs, dac_bits=8)
    channel = UnderwaterAcousticChannel(sample_rate_hz=fs)
    receiver = MatchedFilterReceiver(sample_rate_hz=fs)
    lc_filter = LCReconstructionFilter(inductance_h=68e-6, capacitance_f=150e-9)

    # 1. Synthesize signals
    t_cw, tx_cw, dac_cw = dds.generate_cw_ping(freq_hz=40000, duration_sec=0.005, window="tukey")
    t_lfm, tx_lfm, dac_lfm = dds.generate_lfm_chirp(f_start_hz=35000, f_stop_hz=45000, duration_sec=0.005, window="tukey")

    # 2. Channel propagation (15m target)
    target_range = 15.0
    c = channel.sound_speed_mackenzie(temperature_c=20.0, salinity_ppt=35.0, depth_m=5.0)
    receiver.c = c
    rx_cw, _ = channel.propagate_signal(tx_cw, target_range_m=target_range, snr_db=5.0)
    rx_lfm, _ = channel.propagate_signal(tx_lfm, target_range_m=target_range, snr_db=5.0)

    # 3. Matched filter
    _, env_cw, r_cw = receiver.process_matched_filter(rx_cw, tx_cw)
    _, env_lfm, r_lfm = receiver.process_matched_filter(rx_lfm, tx_lfm)

    # 4. Generate 4-panel plot
    fig, axs = plt.subplots(4, 1, figsize=(11, 10))

    # Panel 1: Time Domain Synthesis
    axs[0].plot(t_cw[:1000] * 1e3, tx_cw[:1000], label="Mode A (40 kHz CW)", color="#1f77b4", alpha=0.8)
    axs[0].plot(t_lfm[:1000] * 1e3, tx_lfm[:1000], label="Mode B (35–45 kHz LFM Chirp)", color="#d62728", alpha=0.8)
    axs[0].set_title("Synthesized Acoustic Transmit Signals (First 2 ms)", fontsize=11, fontweight="bold")
    axs[0].set_xlabel("Time (ms)")
    axs[0].set_ylabel("Normalized Amplitude")
    axs[0].legend(loc="upper right")
    axs[0].grid(True, linestyle="--", alpha=0.6)

    # Panel 2: Power Spectrum
    freqs_cw, pwr_cw = dds.compute_spectrum(tx_cw)
    freqs_lfm, pwr_lfm = dds.compute_spectrum(tx_lfm)
    axs[1].plot(freqs_cw / 1e3, pwr_cw, label="Mode A (CW Monofrequency)", color="#1f77b4")
    axs[1].plot(freqs_lfm / 1e3, pwr_lfm, label="Mode B (LFM Chirp Bandwidth)", color="#d62728")
    axs[1].set_xlim([20, 60])
    axs[1].set_title("Transmit Signal Power Spectral Density", fontsize=11, fontweight="bold")
    axs[1].set_xlabel("Frequency (kHz)")
    axs[1].set_ylabel("Power (dBFS)")
    axs[1].legend(loc="upper right")
    axs[1].grid(True, linestyle="--", alpha=0.6)

    # Panel 3: Matched Filter Pulse Compression
    axs[2].plot(r_cw, env_cw / np.max(env_cw), label="Mode A (CW: 380 cm resolution)", color="#1f77b4", alpha=0.6)
    axs[2].plot(r_lfm, env_lfm / np.max(env_lfm), label="Mode B (LFM: 7.6 cm resolution)", color="#2ca02c")
    axs[2].axvline(target_range, color="red", linestyle=":", label=f"Ground Truth Target ({target_range} m)")
    axs[2].set_xlim([0, 25])
    axs[2].set_title("Matched Filter Echo Range Profile (Pulse Compression)", fontsize=11, fontweight="bold")
    axs[2].set_xlabel("Estimated Range (m)")
    axs[2].set_ylabel("Normalized Envelope")
    axs[2].legend(loc="upper right")
    axs[2].grid(True, linestyle="--", alpha=0.6)

    # Panel 4: LC Filter Bode Response
    f_bode = np.logspace(3, 6, 500)
    mag_db, _ = lc_filter.frequency_response(f_bode)
    axs[3].semilogx(f_bode / 1e3, mag_db, color="#9467bd", linewidth=2)
    axs[3].axvline(40, color="green", linestyle="--", label="40 kHz Sonar Signal (+6.1 dB Passband)")
    axs[3].axvline(250, color="red", linestyle="--", label="250 kHz Class-D PWM (-27.7 dB Stopband)")
    axs[3].set_title("LC Reconstruction Filter (68 µH + 150 nF) Bode Response", fontsize=11, fontweight="bold")
    axs[3].set_xlabel("Frequency (kHz)")
    axs[3].set_ylabel("Gain (dB)")
    axs[3].legend(loc="upper right")
    axs[3].grid(True, which="both", linestyle="--", alpha=0.6)

    plt.tight_layout()
    out_dir = os.path.dirname(output_file)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    plt.savefig(output_file, dpi=150)
    plt.close()
    print(f"[Success] Visualization figure generated at: {output_file}")


if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "../assets/simulation_plots.png")
    generate_all_plots(out_path)
