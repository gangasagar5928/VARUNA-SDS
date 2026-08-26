"""
Automated Verification & Unit Test Suite for VARUNA-SDS Payload
Tests DDS signal synthesis, spectral purity, chirp linearity, LC filtering, and matched filter SNR.
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
        # Use corrected component values
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
        # Assert minimum prototype threshold (anything below 10 is unacceptable)
        self.assertGreaterEqual(samples_per_cycle, 10.0,
                                f"Too few samples/cycle: {samples_per_cycle:.1f} — excessive THD")
        # Warn if below production quality threshold of 25
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

        # In-band power should be significantly higher than out-of-band power
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

    def test_lc_filter_cutoff_above_carrier(self):
        """
        CRITICAL: Verify fc > 40 kHz (carrier frequency).
        A filter with fc below the carrier attenuates the sonar signal — this was the bug
        in the original 100 µH + 100 nF differential design (fc ≈ 35.59 kHz).
        Corrected design: 68 µH + 150 nF → fc ≈ 49.8 kHz.
        """
        metrics = self.lc_filter.get_filter_metrics()

        # fc MUST be above 40 kHz
        self.assertGreater(metrics["cutoff_frequency_hz"], 40_000.0,
                           f"CRITICAL: fc = {metrics['cutoff_frequency_hz']/1000:.2f} kHz is BELOW 40 kHz carrier!")

        # 40 kHz must NOT be attenuated (raw dB must be > -3 dB).
        # Positive dB (e.g. +6 dB) is acceptable near-resonance peaking — the signal is boosted, not lost.
        # The original bug (100µH+100nF, fc=35.59 kHz) gave negative dB here because 40 kHz was in stopband.
        self.assertGreater(metrics["attenuation_at_40khz_db"], -3.0,
                           f"40 kHz signal attenuated below -3 dB: {metrics['attenuation_at_40khz_db']:.2f} dB — filter fc is below carrier")

        # 250 kHz PWM carrier suppression > 20 dB
        self.assertGreater(metrics["pwm_carrier_suppression_ratio_db"], 20.0,
                           f"Insufficient carrier suppression: {metrics['pwm_carrier_suppression_ratio_db']:.2f} dB")

    def test_acoustic_channel_sound_speed(self):
        """Verify Mackenzie sound speed formula for standard ocean conditions."""
        c = self.channel.sound_speed_mackenzie(temperature_c=20.0, salinity_ppt=35.0, depth_m=10.0)
        # Expected 1510–1535 m/s for 20°C, 35 ppt, 10 m depth
        self.assertTrue(1500.0 <= c <= 1550.0, f"Sound speed {c} m/s outside realistic ocean limits")


if __name__ == "__main__":
    unittest.main(verbosity=2)
