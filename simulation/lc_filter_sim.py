"""
Class-D LC Reconstruction Filter Simulator
Models 2nd-order low-pass filter (100 uH + 100 nF) for PAM8302 250 kHz PWM carrier demodulation.
"""

import numpy as np
import scipy.signal as signal
from typing import Tuple, Dict


class LCReconstructionFilter:
    def __init__(self, inductance_h: float = 100e-6, capacitance_f: float = 100e-9, load_resistance_ohm: float = 50.0):
        """
        :param inductance_h: Series inductor per leg (e.g. 100 uH)
        :param capacitance_f: Parallel capacitor (e.g. 100 nF)
        :param load_resistance_ohm: Transducer equivalent parallel resistance at resonance
        """
        self.L = inductance_h * 2.0  # Differential equivalent (two legs in series)
        self.C = capacitance_f
        self.R = load_resistance_ohm

        # Natural resonant frequency: omega_0 = 1 / sqrt(L * C)
        self.omega_0 = 1.0 / np.sqrt(self.L * self.C)
        self.fc_hz = self.omega_0 / (2.0 * np.pi)

        # Damping factor: zeta = 1 / (2 * R) * sqrt(L / C)
        self.damping_zeta = (1.0 / (2.0 * self.R)) * np.sqrt(self.L / self.C)

        # 2nd order transfer function: H(s) = (omega_0^2) / (s^2 + 2*zeta*omega_0*s + omega_0^2)
        num = [self.omega_0 ** 2]
        den = [1.0, 2.0 * self.damping_zeta * self.omega_0, self.omega_0 ** 2]
        self.sys = signal.TransferFunction(num, den)

    def frequency_response(self, freqs_hz: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Compute magnitude (dB) and phase response across frequency range."""
        w = 2.0 * np.pi * freqs_hz
        _, mag, phase = signal.bode(self.sys, w=w)
        return mag, phase

    def filter_signal(self, time_series: np.ndarray, sample_rate_hz: int = 500_000) -> np.ndarray:
        """Apply LC filter dynamics to discrete-time switching waveform."""
        # Convert continuous s-domain system to discrete z-domain via bilinear transform
        discrete_sys = self.sys.to_discrete(dt=1.0 / sample_rate_hz, method="bilinear")
        b = discrete_sys.num
        a = discrete_sys.den
        return signal.lfilter(b, a, time_series)

    def get_filter_metrics(self) -> Dict[str, float]:
        """Calculate key filter specs for acoustic engineering reports."""
        freq_test = np.array([40000.0, 250000.0]) # 40kHz signal vs 250kHz PAM8302 PWM carrier
        mag, _ = self.frequency_response(freq_test)
        
        return {
            "cutoff_frequency_hz": self.fc_hz,
            "damping_ratio": self.damping_zeta,
            "attenuation_at_40khz_db": float(mag[0]),
            "attenuation_at_250khz_carrier_db": float(mag[1]),
            "pwm_carrier_suppression_ratio_db": float(mag[0] - mag[1])
        }


if __name__ == "__main__":
    lc = LCReconstructionFilter(inductance_h=100e-6, capacitance_f=100e-9, load_resistance_ohm=50.0)
    m = lc.get_filter_metrics()
    print(f"[LC Filter] Cutoff Frequency: {m['cutoff_frequency_hz']/1000:.2f} kHz")
    print(f"[LC Filter] 40 kHz Signal Insertion Loss: {m['attenuation_at_40khz_db']:.2f} dB")
    print(f"[LC Filter] 250 kHz PWM Carrier Attenuation: {m['attenuation_at_250khz_carrier_db']:.2f} dB")
    print(f"[LC Filter] Carrier Suppression Margin: {m['pwm_carrier_suppression_ratio_db']:.2f} dB")
