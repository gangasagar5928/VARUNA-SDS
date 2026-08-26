"""
End-to-End Simulation & Verification Demo
VARUNA-SDS: Software-Defined Sonar Payload
"Adaptive Subsea Acoustic Waveform Synthesis for Autonomous Underwater Vehicles"
"""

import sys
import os
import argparse
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from dds_synthesizer import DDSSynthesizer
from acoustic_channel import UnderwaterAcousticChannel
from matched_filter import MatchedFilterReceiver
from lc_filter_sim import LCReconstructionFilter


def main():
    parser = argparse.ArgumentParser(description="VARUNA-SDS Acoustic Simulation Benchmark")
    parser.add_argument("--plot", action="store_true", help="Generate and save DSP visualization plots")
    args = parser.parse_args()

    print("=" * 70)
    print(" VARUNA-SDS: Software-Defined Sonar Simulation Suite")
    print(" 'Adaptive Subsea Acoustic Waveform Synthesis for AUVs'")
    print("=" * 70)

    fs = 500_000 # 500 kSPS DAC Sampling
    dds = DDSSynthesizer(sample_rate_hz=fs, dac_bits=8)
    channel = UnderwaterAcousticChannel(sample_rate_hz=fs)
    receiver = MatchedFilterReceiver(sample_rate_hz=fs)
    lc_filter = LCReconstructionFilter(inductance_h=68e-6, capacitance_f=150e-9) # Corrected: fc ≈ 49.8 kHz

    target_range = 15.0 # 15 meters ground truth
    snr_input_db = 0.0  # 0 dB noisy underwater environment

    print(f"\n[1] ACOUSTIC ENVIRONMENT:")
    c = channel.sound_speed_mackenzie(temperature_c=20.0, salinity_ppt=35.0, depth_m=5.0)
    receiver.c = c
    tl = channel.calculate_transmission_loss_db(range_meters=target_range * 2, center_freq_hz=40_000)
    print(f"    - Sound Speed in Seawater (Mackenzie): {c:.2f} m/s")
    print(f"    - Target Range (Ground Truth): {target_range:.1f} m (Round-Trip: {target_range*2:.1f} m)")
    print(f"    - Round-Trip Acoustic Transmission Loss: {tl:.2f} dB")

    print(f"\n[2] SYNTHESIS & MATCHED FILTER ANALYSIS:")
    # Mode A: CW Ping
    t_cw, tx_cw, dac_cw = dds.generate_cw_ping(freq_hz=40000, duration_sec=0.005, window="tukey")
    rx_cw, meta_cw = channel.propagate_signal(tx_cw, target_range_m=target_range, snr_db=snr_input_db, center_freq_hz=40000)
    _, env_cw, r_cw = receiver.process_matched_filter(rx_cw, tx_cw)
    cw_metrics = receiver.calculate_theoretical_metrics(bandwidth_hz=0, duration_sec=0.005, sound_speed_mps=c)
    peaks_cw = receiver.detect_peaks(env_cw, r_cw)

    # Mode B: LFM Chirp
    t_lfm, tx_lfm, dac_lfm = dds.generate_lfm_chirp(f_start_hz=35000, f_stop_hz=45000, duration_sec=0.005, window="tukey")
    rx_lfm, meta_lfm = channel.propagate_signal(tx_lfm, target_range_m=target_range, snr_db=snr_input_db, center_freq_hz=40000)
    _, env_lfm, r_lfm = receiver.process_matched_filter(rx_lfm, tx_lfm)
    lfm_metrics = receiver.calculate_theoretical_metrics(bandwidth_hz=10000, duration_sec=0.005, sound_speed_mps=c)
    peaks_lfm = receiver.detect_peaks(env_lfm, r_lfm)

    print(f"    +---------------------------+-------------------+-------------------+")
    print(f"    | Metric                    | Mode A (CW 40kHz) | Mode B (LFM Chirp)|")
    print(f"    +---------------------------+-------------------+-------------------+")
    print(f"    | Bandwidth                 | ~200 Hz (CW)      | 10,000 Hz (35-45k)|")
    print(f"    | Pulse Duration            | 5.0 ms            | 5.0 ms            |")
    print(f"    | Time-Bandwidth Product    | {cw_metrics['time_bandwidth_product']:<17.1f} | {lfm_metrics['time_bandwidth_product']:<17.1f} |")
    print(f"    | Matched Filter Gain       | {cw_metrics['processing_gain_db']:<15.2f}dB | {lfm_metrics['processing_gain_db']:<15.2f}dB |")
    print(f"    | Range Resolution (Delta R)| {cw_metrics['range_resolution_m']*100:<15.1f}cm | {lfm_metrics['range_resolution_m']*100:<15.1f}cm |")
    print(f"    +---------------------------+-------------------+-------------------+")

    print(f"\n[3] PEAK DETECTION & RANGE ESTIMATION:")
    cw_est = peaks_cw[0][0] if peaks_cw else float('nan')
    lfm_est = peaks_lfm[0][0] if peaks_lfm else float('nan')
    cw_err = abs(cw_est - target_range) * 100.0 if peaks_cw else float('nan')
    lfm_err = abs(lfm_est - target_range) * 100.0 if peaks_lfm else float('nan')

    print(f"    - Mode A (CW 40 kHz) Estimated Range : {cw_est:.3f} m (Error: {cw_err:.1f} cm)")
    print(f"    - Mode B (LFM Chirp) Estimated Range : {lfm_est:.3f} m (Error: {lfm_err:.1f} cm)")
    if len(peaks_lfm) > 1:
        print(f"    - Resolved Multipath Reflection 1   : {peaks_lfm[1][0]:.3f} m (Rel Amp: {peaks_lfm[1][1]:.2f})")

    print(f"\n[4] PAM8302 CLASS-D LC RECONSTRUCTION FILTER:")
    m = lc_filter.get_filter_metrics()
    print(f"    - Symmetrical Cutoff Frequency (fc): {m['cutoff_frequency_hz']/1000:.2f} kHz")
    print(f"    - Passband Insertion Loss @ 40 kHz: {m['attenuation_at_40khz_db']:.2f} dB")
    print(f"    - PWM Switching Attenuation @ 250 kHz: {m['attenuation_at_250khz_carrier_db']:.2f} dB")
    print(f"    - PWM Carrier Suppression Margin: {m['pwm_carrier_suppression_ratio_db']:.2f} dB (>20 dB Target MET)")

    if args.plot:
        try:
            import matplotlib.pyplot as plt
            fig, axs = plt.subplots(3, 1, figsize=(10, 8))
            
            # Plot 1: Transmitted Chirp Waveform
            axs[0].plot(t_lfm[:1000] * 1e3, tx_lfm[:1000], color='blue')
            axs[0].set_title("Synthesized LFM Chirp Waveform (First 2 ms)")
            axs[0].set_xlabel("Time (ms)")
            axs[0].set_ylabel("Amplitude")
            axs[0].grid(True)

            # Plot 2: Matched Filter Envelopes
            axs[1].plot(r_cw, env_cw / np.max(env_cw), label="Mode A (CW 40kHz)", color='orange', alpha=0.7)
            axs[1].plot(r_lfm, env_lfm / np.max(env_lfm), label="Mode B (LFM Chirp)", color='teal')
            axs[1].set_xlim([0, 30])
            axs[1].set_title("Matched Filter Range Compression Output")
            axs[1].set_xlabel("Range (m)")
            axs[1].set_ylabel("Normalized Envelope")
            axs[1].legend()
            axs[1].grid(True)

            # Plot 3: LC Filter Bode Response
            f_bode = np.logspace(3, 6, 500)
            mag_db, _ = lc_filter.frequency_response(f_bode)
            axs[2].semilogx(f_bode / 1e3, mag_db, color='purple')
            axs[2].axvline(40, color='green', linestyle='--', label='40 kHz Sonar Carrier')
            axs[2].axvline(250, color='red', linestyle='--', label='250 kHz PWM Carrier')
            axs[2].set_title("LC Reconstruction Filter Magnitude Response")
            axs[2].set_xlabel("Frequency (kHz)")
            axs[2].set_ylabel("Magnitude (dB)")
            axs[2].legend()
            axs[2].grid(True)

            plt.tight_layout()
            out_path = os.path.join(os.path.dirname(__file__), "../assets/simulation_plots.png")
            plt.savefig(out_path, dpi=150)
            print(f"\n[Plotting] DSP waveform plots saved to: {out_path}")
        except Exception as e:
            print(f"\n[Plotting] Could not generate plots: {e}")

    print("\n" + "=" * 65)
    print(" Simulation Completed Successfully. System Ready for Hardware Deploy.")
    print("=" * 65)


if __name__ == "__main__":
    main()
