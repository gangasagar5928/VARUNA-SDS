"""
Matched Filter & Pulse Compression Receiver Engine
Demonstrates acoustic processing gain (10*log10(BT)) and range resolution of LFM Chirps vs CW Pings.
"""

import numpy as np
import scipy.signal as signal
from typing import Tuple, Dict


class MatchedFilterReceiver:
    def __init__(self, sample_rate_hz: int = 500_000, sound_speed_mps: float = 1500.0):
        self.fs = sample_rate_hz
        self.c = sound_speed_mps

    def process_matched_filter(
        self,
        rx_signal: np.ndarray,
        reference_tx: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Perform fast cross-correlation matched filtering and Hilbert envelope extraction.
        :param rx_signal: Raw received acoustic time series
        :param reference_tx: Transmitted replica template
        :return: (time_axis, compressed_envelope, range_axis_meters)
        """
        # Matched filter via scipy cross-correlation
        correlation = signal.correlate(rx_signal, reference_tx, mode="full")
        
        # Analytic signal envelope via Hilbert transform
        analytic = signal.hilbert(correlation)
        envelope = np.abs(analytic)

        # Align time axis to start of correlation
        dt = 1.0 / self.fs
        num_points = len(envelope)
        time_axis = np.arange(0, num_points) * dt - (len(reference_tx) * dt)
        
        # Convert time of flight to target range: r = (c * t) / 2
        range_axis = np.maximum(0.0, (self.c * time_axis) / 2.0)

        return time_axis, envelope, range_axis

    def detect_peaks(
        self,
        envelope: np.ndarray,
        range_axis: np.ndarray,
        threshold_db_below_max: float = 15.0,
        min_distance_samples: int = 50
    ) -> list:
        """
        Extract echo peaks and estimated ranges.
        """
        max_val = np.max(envelope) + 1e-12
        env_norm = envelope / max_val
        threshold = 10.0 ** (-threshold_db_below_max / 20.0)

        peaks, props = signal.find_peaks(
            env_norm,
            height=threshold,
            distance=min_distance_samples,
            prominence=0.1
        )

        detections = []
        for p in peaks:
            r = range_axis[p]
            amp = env_norm[p]
            detections.append((float(r), float(amp)))
        return detections

    @staticmethod
    def calculate_theoretical_metrics(bandwidth_hz: float, duration_sec: float, sound_speed_mps: float = 1500.0) -> Dict[str, float]:
        """
        Compute theoretical processing gain and range resolution.
        """
        time_bandwidth_product = max(1.0, bandwidth_hz * duration_sec)
        processing_gain_db = 10.0 * np.log10(time_bandwidth_product)
        
        # Range resolution: delta_R = c / (2 * B)
        if bandwidth_hz > 0:
            range_resolution_m = sound_speed_mps / (2.0 * bandwidth_hz)
        else:
            range_resolution_m = (sound_speed_mps * duration_sec) / 2.0

        return {
            "time_bandwidth_product": time_bandwidth_product,
            "processing_gain_db": processing_gain_db,
            "range_resolution_m": range_resolution_m
        }


if __name__ == "__main__":
    from dds_synthesizer import DDSSynthesizer
    from acoustic_channel import UnderwaterAcousticChannel

    dds = DDSSynthesizer(sample_rate_hz=500_000)
    channel = UnderwaterAcousticChannel(sample_rate_hz=500_000)
    rx_engine = MatchedFilterReceiver(sample_rate_hz=500_000)

    # 1. Test LFM Chirp
    _, tx_chirp, _ = dds.generate_lfm_chirp(35000, 45000, 0.005)
    rx_chirp, meta = channel.propagate_signal(tx_chirp, target_range_m=12.5, snr_db=5.0)
    t_ax, env_chirp, r_ax = rx_engine.process_matched_filter(rx_chirp, tx_chirp)
    metrics = rx_engine.calculate_theoretical_metrics(bandwidth_hz=10000, duration_sec=0.005)

    print(f"[Matched Filter] Theoretical LFM Processing Gain: {metrics['processing_gain_db']:.2f} dB")
    print(f"[Matched Filter] Theoretical Range Resolution: {metrics['range_resolution_m']*100:.2f} cm")
    print(f"[Matched Filter] Ground Truth Range: {meta['target_range_m']} m")
