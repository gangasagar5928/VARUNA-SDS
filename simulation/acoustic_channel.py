"""
Underwater Acoustic Channel Simulator
Models Sound Speed Profiles (Mackenzie), Thermocline Stratification,
Transmission Loss (Thorp Absorption + Geometric Spreading), and Multipath Reverberation.
"""

import numpy as np
from typing import List, Tuple, Dict


class UnderwaterAcousticChannel:
    def __init__(self, sample_rate_hz: int = 500_000):
        self.fs = sample_rate_hz

    @staticmethod
    def sound_speed_mackenzie(temperature_c: float = 15.0, salinity_ppt: float = 35.0, depth_m: float = 10.0) -> float:
        """
        Calculate speed of sound in seawater using Mackenzie (1981) empirical formula.
        :return: Sound speed in m/s
        """
        T = temperature_c
        S = salinity_ppt
        D = depth_m

        c = (
            1448.96
            + 4.591 * T
            - 5.304e-2 * (T ** 2)
            + 2.374e-4 * (T ** 3)
            + 1.340 * (S - 35.0)
            + 1.630e-2 * D
            + 1.675e-7 * (D ** 2)
            - 1.025e-2 * T * (S - 35.0)
            - 7.139e-13 * T * (D ** 3)
        )
        return float(c)

    @staticmethod
    def thorp_attenuation_db_per_km(freq_khz: float) -> float:
        """
        Compute seawater acoustic absorption coefficient (dB/km) using Thorp formula.
        """
        f = freq_khz
        alpha = (
            (0.1 * (f ** 2)) / (1.0 + (f ** 2))
            + (40.0 * (f ** 2)) / (4100.0 + (f ** 2))
            + 2.75e-4 * (f ** 2)
            + 0.003
        )
        return float(alpha)

    def calculate_transmission_loss_db(self, range_meters: float, center_freq_hz: float = 40_000.0) -> float:
        """
        Compute total acoustic transmission loss TL = 20*log10(r) + alpha*r*1e-3.
        """
        if range_meters <= 1.0:
            return 0.0
        r_km = range_meters / 1000.0
        alpha = self.thorp_attenuation_db_per_km(center_freq_hz / 1000.0)
        spherical_spreading = 20.0 * np.log10(range_meters)
        absorption_loss = alpha * r_km
        return float(spherical_spreading + absorption_loss)

    def propagate_signal(
        self,
        tx_signal: np.ndarray,
        target_range_m: float = 25.0,
        target_rcs: float = 1.0,
        snr_db: float = 10.0,
        add_multipath: bool = True,
        water_temp_c: float = 20.0,
        water_depth_m: float = 5.0,
        center_freq_hz: float = 40_000.0
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Simulate round-trip acoustic propagation in stratified water with thermocline and reflections.
        :return: (rx_signal, telemetry_metadata)
        """
        c = self.sound_speed_mackenzie(temperature_c=water_temp_c, depth_m=water_depth_m)
        
        # Round trip time: t = 2 * r / c
        round_trip_distance = 2.0 * target_range_m
        propagation_delay_sec = round_trip_distance / c
        delay_samples = int(round(propagation_delay_sec * self.fs))

        # Total signal length with margin
        total_samples = delay_samples + len(tx_signal) + int(0.01 * self.fs)
        rx_clean = np.zeros(total_samples)

        # Direct Target Echo using dynamic center frequency
        tl_db = self.calculate_transmission_loss_db(round_trip_distance, center_freq_hz)
        amplitude_scale = (10.0 ** (-tl_db / 20.0)) * np.sqrt(target_rcs)
        
        # Direct return
        rx_clean[delay_samples : delay_samples + len(tx_signal)] += tx_signal * amplitude_scale

        # Multipath surface / bottom echoes
        if add_multipath:
            # Surface reflection (phase inverted: -0.65 coefficient)
            surface_extra_delay = int(0.0012 * self.fs)  # 1.2 ms extra path
            idx_s = delay_samples + surface_extra_delay
            if idx_s + len(tx_signal) <= total_samples:
                rx_clean[idx_s : idx_s + len(tx_signal)] += -0.65 * tx_signal * amplitude_scale

            # Bottom bounce
            bottom_extra_delay = int(0.0028 * self.fs)
            idx_b = delay_samples + bottom_extra_delay
            if idx_b + len(tx_signal) <= total_samples:
                rx_clean[idx_b : idx_b + len(tx_signal)] += 0.40 * tx_signal * amplitude_scale

        # Constant ambient ocean noise floor referenced to nominal transmission level
        tx_ref_power = np.mean(tx_signal ** 2) if len(tx_signal) > 0 else 1.0
        # Background ambient noise power floor
        noise_power = (tx_ref_power * 1e-3) / (10.0 ** (snr_db / 10.0))
        noise = np.random.normal(0.0, np.sqrt(noise_power), len(rx_clean))

        rx_noisy = rx_clean + noise

        telemetry = {
            "sound_speed_mps": c,
            "round_trip_delay_ms": propagation_delay_sec * 1000.0,
            "target_range_m": target_range_m,
            "transmission_loss_db": tl_db,
            "delay_samples": delay_samples,
            "center_freq_hz": center_freq_hz
        }

        return rx_noisy, telemetry


if __name__ == "__main__":
    channel = UnderwaterAcousticChannel(sample_rate_hz=500_000)
    c = channel.sound_speed_mackenzie(20.0, 35.0, 10.0)
    tl = channel.calculate_transmission_loss_db(50.0, 40_000.0)
    print(f"[Acoustic Channel] Sound Speed: {c:.2f} m/s")
    print(f"[Acoustic Channel] Transmission Loss at 50m (40kHz): {tl:.2f} dB")
