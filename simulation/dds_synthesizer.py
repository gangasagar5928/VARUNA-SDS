"""
DDS (Direct Digital Synthesis) Waveform Generator & Acoustic Synthesizer
VARUNA-SDS: Software-Defined Sonar Payload (MoES)
"""

import numpy as np
import scipy.signal as signal
from typing import Tuple, Optional


class DDSSynthesizer:
    def __init__(self, sample_rate_hz: int = 500_000, dac_bits: int = 8):
        """
        Initialize Direct Digital Synthesis generator.
        :param sample_rate_hz: DAC sampling frequency in Hz (Default: 500 kSPS)
        :param dac_bits: Quantization resolution in bits (Default: 8-bit MCU DAC)
        """
        self.fs = sample_rate_hz
        self.dac_bits = dac_bits
        self.max_dac_val = (1 << dac_bits) - 1
        self.mid_dac_val = (1 << (dac_bits - 1))

    def _apply_window(self, samples: np.ndarray, window: str = "tukey") -> np.ndarray:
        """Apply amplitude taper to minimize spectral leakage and transducer ringing."""
        N = len(samples)
        if window.lower() == "tukey":
            win = signal.windows.tukey(N, alpha=0.2)
        elif window.lower() == "hann":
            win = np.hanning(N)
        elif window.lower() == "hamming":
            win = np.hamming(N)
        elif window.lower() == "rectangular":
            win = np.ones(N)
        else:
            raise ValueError(f"Unknown window: {window}")
        return samples * win

    def generate_cw_ping(
        self,
        freq_hz: float = 40_000.0,
        duration_sec: float = 0.005,
        window: str = "tukey"
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate Monofrequency CW Ping (Mode A).
        :return: (time_array, analog_signal, quantized_dac_buffer)
        """
        t = np.arange(0, duration_sec, 1.0 / self.fs)
        analog_raw = np.sin(2.0 * np.pi * freq_hz * t)
        analog_win = self._apply_window(analog_raw, window)

        # Quantize to unsigned DAC buffer
        quantized = np.clip(
            np.round(self.mid_dac_val + (self.mid_dac_val - 4) * analog_win),
            0,
            self.max_dac_val
        ).astype(np.uint8 if self.dac_bits == 8 else np.uint16)

        return t, analog_win, quantized

    def generate_lfm_chirp(
        self,
        f_start_hz: float = 35_000.0,
        f_stop_hz: float = 45_000.0,
        duration_sec: float = 0.005,
        window: str = "tukey"
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate Linear Frequency Modulation (LFM) Chirp (Mode B).
        Instantaneous Frequency: f(t) = f_start + ((f_stop - f_start) / T) * t
        Phase: phi(t) = 2*pi * (f_start * t + 0.5 * k * t^2)
        :return: (time_array, analog_signal, quantized_dac_buffer)
        """
        t = np.arange(0, duration_sec, 1.0 / self.fs)
        k = (f_stop_hz - f_start_hz) / duration_sec  # Chirp rate in Hz/s
        phase = 2.0 * np.pi * (f_start_hz * t + 0.5 * k * (t ** 2))
        analog_raw = np.sin(phase)
        analog_win = self._apply_window(analog_raw, window)

        # Quantize to unsigned DAC buffer
        quantized = np.clip(
            np.round(self.mid_dac_val + (self.mid_dac_val - 4) * analog_win),
            0,
            self.max_dac_val
        ).astype(np.uint8 if self.dac_bits == 8 else np.uint16)

        return t, analog_win, quantized

    def compute_spectrum(self, signal_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Compute single-sided power spectrum in dB."""
        N = len(signal_data)
        fft_vals = np.fft.rfft(signal_data)
        freqs = np.fft.rfftfreq(N, 1.0 / self.fs)
        magnitude_db = 20 * np.log10(np.abs(fft_vals) / (N / 2) + 1e-12)
        return freqs, magnitude_db


if __name__ == "__main__":
    dds = DDSSynthesizer(sample_rate_hz=500_000, dac_bits=8)
    t_cw, sig_cw, dac_cw = dds.generate_cw_ping(freq_hz=40000, duration_sec=0.005)
    t_lfm, sig_lfm, dac_lfm = dds.generate_lfm_chirp(f_start_hz=35000, f_stop_hz=45000, duration_sec=0.005)

    print(f"[DDS Engine] Generated CW Ping: {len(dac_cw)} samples (Duration: {t_cw[-1]*1000:.2f} ms)")
    print(f"[DDS Engine] Generated LFM Chirp: {len(dac_lfm)} samples (35kHz -> 45kHz)")
    print(f"[DDS Engine] DAC Buffer Sample Preview (First 10): {dac_lfm[:10].tolist()}")
