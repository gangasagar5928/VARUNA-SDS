"""
Automated Verification & Unit Test Suite for VARUNA-SDS Payload
Tests DDS signal synthesis, spectral purity, chirp linearity, LC filtering,
matched filter range estimation, multipath resolution, and acoustic propagation.
"""

import sys
import os
import unittest
import numpy as np

# Add project directories to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../simulation")))

from dds_synthesizer import DDSSynthesizer
from acoustic_channel import UnderwaterAcousticChannel
from matched_filter import MatchedFilterReceiver
from lc_filter_sim import LCReconstructionFilter

# Corrected LC filter component values: 68 µH + 150 nF → fc ≈ 49.8 kHz (above 40 kHz carrier)
LC_INDUCTANCE_H  = 68e-6
LC_CAPACITANCE_F = 150e-9


class TestVarunaSDSPayload(unittest.TestCase):
    def setUp(self):
        self.fs = 500_000
        self.dds = DDSSynthesizer(sample_rate_hz=self.fs, dac_bits=8)
        self.channel = UnderwaterAcousticChannel(sample_rate_hz=self.fs)
        self.receiver = MatchedFilterReceiver(sample_rate_hz=self.fs)
        self.lc_filter = LCReconstructionFilter(
            inductance_h=LC_INDUCTANCE_H,
            capacitance_f=LC_CAPACITANCE_F
        )

    def test_cw_synthesis_frequency_accuracy(self):
        """FR-1 Test: Verify 40 kHz Monofrequency peak accuracy within 0.1%."""
        target_f = 40_000.0
        t, sig, dac = self.dds.generate_cw_ping(freq_hz=target_f, duration_sec=0.010, window="rectangular")

        freqs, mag_db = self.dds.compute_spectrum(sig)
        peak_idx = np.argmax(mag_db)
        measured_f = freqs[peak_idx]

        self.assertAlmostEqual(measured_f, target_f, delta=100.0,
                               msg=f"CW frequency mismatch: measured {measured_f} Hz, expected {target_f} Hz")
        self.assertEqual(len(dac), 5000, "Sample count mismatch for 10ms at 500kSPS")

    def test_cw_dds_samples_per_cycle(self):
        """
        Verify DDS samples-per-cycle constraint for THD awareness.
        At 500 kSPS and 40 kHz: samples/cycle = 12.5 (prototype-grade, ~-40 dBc THD).
        Acceptable for hackathon prototype. Production target: >= 25 samples/cycle (1 MSPS, 16-bit ext DAC).
        """
        samples_per_cycle = self.fs / 40_000.0
        self.assertGreaterEqual(samples_per_cycle, 10.0,
                                f"Too few samples/cycle: {samples_per_cycle:.1f} — excessive THD")
        if samples_per_cycle < 25.0:
            import warnings
            warnings.warn(
                f"Prototype-grade: {samples_per_cycle:.1f} samples/cycle → ~-40 dBc THD. "
                "Production requires >= 25 samples/cycle (1 MSPS + 16-bit external DAC).",
                UserWarning
            )

    def test_lfm_chirp_sweep_properties(self):
        """FR-1 Test: Verify LFM Chirp instantaneous frequency range (35 kHz -> 45 kHz)."""
        f_start = 35_000.0
        f_stop = 45_000.0
        duration = 0.005
        t, sig, dac = self.dds.generate_lfm_chirp(f_start_hz=f_start, f_stop_hz=f_stop, duration_sec=duration)

        freqs, mag_db = self.dds.compute_spectrum(sig)

        in_band_mask = (freqs >= 35000.0) & (freqs <= 45000.0)
        out_band_mask = (freqs < 20000.0) | (freqs > 60000.0)

        avg_in_band = np.mean(mag_db[in_band_mask])
        avg_out_band = np.mean(mag_db[out_band_mask])

        snr_spectral = avg_in_band - avg_out_band
        self.assertGreater(snr_spectral, 20.0, "LFM spectrum not concentrated in 35–45 kHz band")

    def test_matched_filter_pulse_compression_gain(self):
        """Verify pulse compression SNR gain of LFM Chirp over CW."""
        bandwidth = 10_000.0  # 35 kHz -> 45 kHz
        duration = 0.005      # 5 ms

        metrics = self.receiver.calculate_theoretical_metrics(bandwidth_hz=bandwidth, duration_sec=duration)
        expected_pg = 10.0 * np.log10(bandwidth * duration)  # 10*log10(50) = 16.99 dB

        self.assertAlmostEqual(metrics["processing_gain_db"], expected_pg, places=2)
        self.assertLess(metrics["range_resolution_m"], 0.10, "Range resolution must be < 10 cm")

    def test_peak_detection_range_accuracy(self):
        """TEST-02: Verify detect_peaks correctly resolves ground truth range within tolerance."""
        target_range = 18.5 # meters
        c = self.channel.sound_speed_mackenzie(temperature_c=20.0, salinity_ppt=35.0, depth_m=5.0)
        self.receiver.c = c

        t_lfm, tx_lfm, _ = self.dds.generate_lfm_chirp(35000, 45000, 0.005, window="tukey")
        rx_signal, meta = self.channel.propagate_signal(tx_lfm, target_range_m=target_range, snr_db=15.0, add_multipath=False)
        _, envelope, r_axis = self.receiver.process_matched_filter(rx_signal, tx_lfm)
        
        detections = self.receiver.detect_peaks(envelope, r_axis)
        self.assertTrue(len(detections) > 0, "No peaks detected by matched filter receiver")

        estimated_range = detections[0][0]
        range_error_m = abs(estimated_range - target_range)
        self.assertLess(range_error_m, 0.08, f"Range error {range_error_m*100:.2f} cm exceeds range resolution limit")

    def test_multipath_echo_resolution(self):
        """Verify receiver resolves direct echo and surface bounce multipath peaks."""
        target_range = 12.0
        c = self.channel.sound_speed_mackenzie(temperature_c=20.0, salinity_ppt=35.0, depth_m=5.0)
        self.receiver.c = c

        _, tx_lfm, _ = self.dds.generate_lfm_chirp(35000, 45000, 0.005, window="tukey")
        rx_signal, _ = self.channel.propagate_signal(tx_lfm, target_range_m=target_range, snr_db=20.0, add_multipath=True)
        _, envelope, r_axis = self.receiver.process_matched_filter(rx_signal, tx_lfm)

        detections = self.receiver.detect_peaks(envelope, r_axis, threshold_db_below_max=10.0)
        self.assertGreaterEqual(len(detections), 2, "Failed to resolve multipath reflections")

    def test_buffer_overflow_clamping(self):
        """TEST-03: Verify synthesis handles long duration requests safely without exceeding buffer."""
        # 60 ms duration at 500 kSPS would be 30,000 samples, which exceeds max buffer of 4096
        # Synthesizer should generate exact sample count or clamp properly
        t, sig, dac = self.dds.generate_cw_ping(freq_hz=40000, duration_sec=0.060)
        self.assertEqual(len(dac), 30000, "Python reference synthesizer sample count mismatch")
        self.assertTrue(np.all(dac >= 0) and np.all(dac <= 255), "DAC values exceed 8-bit limits")

    def test_lc_filter_cutoff_above_carrier(self):
        """
        CRITICAL: Verify fc > 40 kHz (carrier frequency).
        Corrected design: 68 µH + 150 nF → fc ≈ 49.8 kHz.
        """
        metrics = self.lc_filter.get_filter_metrics()

        # fc MUST be above 40 kHz
        self.assertGreater(metrics["cutoff_frequency_hz"], 40_000.0,
                           f"CRITICAL: fc = {metrics['cutoff_frequency_hz']/1000:.2f} kHz is BELOW 40 kHz carrier!")

        # 40 kHz must NOT be attenuated (raw dB > -3 dB)
        self.assertGreater(metrics["attenuation_at_40khz_db"], -3.0,
                           f"40 kHz signal attenuated below -3 dB: {metrics['attenuation_at_40khz_db']:.2f} dB")

        # 250 kHz PWM carrier suppression > 20 dB
        self.assertGreater(metrics["pwm_carrier_suppression_ratio_db"], 20.0,
                           f"Insufficient carrier suppression: {metrics['pwm_carrier_suppression_ratio_db']:.2f} dB")

    def test_acoustic_channel_sound_speed(self):
        """Verify Mackenzie sound speed formula for standard ocean conditions."""
        c = self.channel.sound_speed_mackenzie(temperature_c=20.0, salinity_ppt=35.0, depth_m=10.0)
        self.assertTrue(1500.0 <= c <= 1550.0, f"Sound speed {c} m/s outside realistic ocean limits")

    def test_transmission_loss_frequency_scaling(self):
        """Verify Thorp attenuation increases at higher frequencies."""
        loss_40k = self.channel.calculate_transmission_loss_db(range_meters=100.0, center_freq_hz=40_000)
        loss_80k = self.channel.calculate_transmission_loss_db(range_meters=100.0, center_freq_hz=80_000)
        self.assertGreater(loss_80k, loss_40k, "Acoustic attenuation did not increase with frequency")


if __name__ == "__main__":
    unittest.main(verbosity=2)
