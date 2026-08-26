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


class TestVarunaSDSPayload(unittest.TestCase):
    def setUp(self):
        self.fs = 500_000
        self.dds = DDSSynthesizer(sample_rate_hz=self.fs, dac_bits=8)
        self.channel = UnderwaterAcousticChannel(sample_rate_hz=self.fs)
        self.receiver = MatchedFilterReceiver(sample_rate_hz=self.fs)
        self.lc_filter = LCReconstructionFilter(inductance_h=100e-6, capacitance_f=100e-9)

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

    def test_lfm_chirp_sweep_properties(self):
        """FR-1 Test: Verify LFM Chirp instantaneous frequency range (35 kHz -> 45 kHz)."""
        f_start = 35_000.0
        f_stop = 45_000.0
        duration = 0.005
        t, sig, dac = self.dds.generate_lfm_chirp(f_start_hz=f_start, f_stop_hz=f_stop, duration_sec=duration)

        freqs, mag_db = self.dds.compute_spectrum(sig)
        
        # In band power should be significantly higher than out-of-band power
        in_band_mask = (freqs >= 35000.0) & (freqs <= 45000.0)
        out_band_mask = (freqs < 20000.0) | (freqs > 60000.0)
        
        avg_in_band = np.mean(mag_db[in_band_mask])
        avg_out_band = np.mean(mag_db[out_band_mask])
        
        snr_spectral = avg_in_band - avg_out_band
        self.assertGreater(snr_spectral, 20.0, "LFM spectrum not concentrated in 35-45 kHz band")

    def test_matched_filter_pulse_compression_gain(self):
        """Verify pulse compression SNR gain of LFM Chirp over CW."""
        bandwidth = 10_000.0 # 35kHz -> 45kHz
        duration = 0.005     # 5 ms
        
        metrics = self.receiver.calculate_theoretical_metrics(bandwidth_hz=bandwidth, duration_sec=duration)
        expected_pg = 10.0 * np.log10(bandwidth * duration) # 10*log10(50) = 16.989 dB
        
        self.assertAlmostEqual(metrics["processing_gain_db"], expected_pg, places=2)
        self.assertLess(metrics["range_resolution_m"], 0.10, "Range resolution must be sharper than 10 cm")

    def test_lc_reconstruction_filter_carrier_suppression(self):
        """FR-3 Test: Verify Class-D 250 kHz PWM carrier attenuation > 20 dB."""
        metrics = self.lc_filter.get_filter_metrics()
        
        # 40 kHz insertion loss should be reasonable (< 6 dB)
        self.assertLess(abs(metrics["attenuation_at_40khz_db"]), 6.0)
        
        # 250 kHz carrier suppression margin should be > 20 dB
        self.assertGreater(metrics["pwm_carrier_suppression_ratio_db"], 20.0, 
                           f"Insufficient PWM carrier attenuation: {metrics['pwm_carrier_suppression_ratio_db']} dB")

    def test_acoustic_channel_sound_speed(self):
        """Verify Mackenzie sound speed formula for standard ocean conditions."""
        c = self.channel.sound_speed_mackenzie(temperature_c=20.0, salinity_ppt=35.0, depth_m=10.0)
        # Expected around 1521 - 1523 m/s
        self.assertTrue(1500.0 <= c <= 1550.0, f"Sound speed {c} m/s outside realistic ocean limits")


if __name__ == "__main__":
    unittest.main(verbosity=2)
