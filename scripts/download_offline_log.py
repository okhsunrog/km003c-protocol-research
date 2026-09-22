#!/usr/bin/env python3
"""
Download offline ADC logs from POWER-Z KM003C.

This script:
1. Connects to the device and authenticates with its HardwareID
2. Requests the log catalog (attribute 0x0200)
3. Downloads the encrypted log data with MemoryRead
4. Parses and displays the ADC samples

The MemoryRead/StreamingAuth framing lives in `km003c_analysis.device`, and the
catalog and sample layouts are parsed by the Rust bindings where the installed
version provides them.

Usage:
    uv run --locked scripts/download_offline_log.py
    uv run --locked scripts/download_offline_log.py --output log_data.csv
"""

import argparse
import struct
import time
from dataclasses import dataclass

import km003c

from km003c_analysis.device import (
    ADDR_CALIBRATION,
    ADDR_DEVICE_INFO,
    ADDR_FIRMWARE_INFO,
    ADDR_HARDWARE_ID,
    ADDR_OFFLINE_LOG,
    HARDWARE_ID_SIZE,
    INFO_BLOCK_SIZE,
    LOG_METADATA_SIZE,
    OFFLINE_LOG_SAMPLE_SIZE,
    Km003cUsb,
)

# Initialization reads used by the official application.
INIT_MEMORY_READS = [
    (ADDR_DEVICE_INFO, INFO_BLOCK_SIZE),
    (ADDR_FIRMWARE_INFO, INFO_BLOCK_SIZE),
    (ADDR_CALIBRATION, INFO_BLOCK_SIZE),
    (ADDR_HARDWARE_ID, HARDWARE_ID_SIZE),
]

# GetData attribute for the offline log catalog, in wire encoding.
WIRE_ATT_LOG_METADATA = 0x0400
WIRE_ATT_PD_PACKET = 0x0020
WIRE_ATT_SETTINGS = 0x0010


@dataclass
class LogMetadata:
    """Offline log metadata from attribute 0x0200."""

    name: str
    sample_count: int
    interval_ms: int
    flags: int
    recorded_duration_seconds: int
    unknown_0x10: int
    final_charge_uah: int
    final_energy_uwh: int
    data_offset: int
    reserved_tail: bytes

    @property
    def duration_seconds(self) -> float:
        """Elapsed time between the first and last recorded samples."""
        return max(self.sample_count - 1, 0) * self.interval_ms / 1000

    @property
    def data_size(self) -> int:
        """Actual data size (16 bytes per sample)."""
        return self.sample_count * OFFLINE_LOG_SAMPLE_SIZE

    @property
    def data_address(self) -> int:
        """MemoryRead address for this catalog entry."""
        return ADDR_OFFLINE_LOG + self.data_offset

    @classmethod
    def from_bytes(cls, entry: bytes) -> "LogMetadata":
        """Parse one 48-byte catalog entry."""
        if len(entry) != LOG_METADATA_SIZE:
            raise ValueError(
                f"LogMetadata entry must be {LOG_METADATA_SIZE} bytes, got {len(entry)}"
            )
        return cls(
            name=entry[0:16].split(b"\x00")[0].decode("ascii", errors="replace"),
            unknown_0x10=struct.unpack_from("<H", entry, 16)[0],
            sample_count=struct.unpack_from("<H", entry, 18)[0],
            interval_ms=struct.unpack_from("<H", entry, 20)[0],
            flags=struct.unpack_from("<H", entry, 22)[0],
            recorded_duration_seconds=struct.unpack_from("<I", entry, 24)[0],
            final_charge_uah=struct.unpack_from("<i", entry, 28)[0],
            final_energy_uwh=struct.unpack_from("<i", entry, 32)[0],
            data_offset=struct.unpack_from("<I", entry, 36)[0],
            reserved_tail=entry[40:48],
        )


@dataclass
class AdcSample:
    """Single ADC sample from offline log."""

    voltage_uv: int  # Microvolts
    current_ua: int  # Microamps (negative = discharge)
    charge_acc_uah: int  # Accumulated charge in µAh
    energy_acc_uwh: int  # Accumulated energy in µWh

    @property
    def voltage_v(self) -> float:
        return self.voltage_uv / 1_000_000

    @property
    def current_a(self) -> float:
        return self.current_ua / 1_000_000

    @property
    def charge_mah(self) -> float:
        return self.charge_acc_uah / 1000

    @property
    def energy_mwh(self) -> float:
        return self.energy_acc_uwh / 1000


def parse_samples(data: bytes) -> list[AdcSample]:
    """Parse decrypted data into ADC samples."""
    if len(data) % OFFLINE_LOG_SAMPLE_SIZE:
        raise ValueError(
            f"Offline log length must be a multiple of {OFFLINE_LOG_SAMPLE_SIZE}, got {len(data)}"
        )
    samples = []
    for offset in range(0, len(data), OFFLINE_LOG_SAMPLE_SIZE):
        voltage, current, charge, energy = struct.unpack_from("<iiii", data, offset)
        samples.append(
            AdcSample(
                voltage_uv=voltage,
                current_ua=current,
                charge_acc_uah=charge,
                energy_acc_uwh=energy,
            )
        )
    return samples


def parse_catalog(response: bytes) -> list[LogMetadata]:
    """Parse a PutData response carrying the offline log catalog."""
    if len(response) < 8 or response[0] & 0x7F != 0x41:
        return []

    payload = response[8:]
    if len(payload) % LOG_METADATA_SIZE:
        raise ValueError(
            f"LogMetadata payload must contain {LOG_METADATA_SIZE}-byte entries, "
            f"got {len(payload)} bytes"
        )
    return [
        LogMetadata.from_bytes(payload[offset : offset + LOG_METADATA_SIZE])
        for offset in range(0, len(payload), LOG_METADATA_SIZE)
    ]


class OfflineLogDownloader:
    """Drives the init, authentication and download sequence."""

    def __init__(self, device: Km003cUsb) -> None:
        self.device = device

    def initialize(self) -> None:
        """Run the initialization sequence the official application uses."""
        print("Running initialization sequence...")
        self.device.connect()
        time.sleep(0.05)

        hardware_id = b""
        for address, size in INIT_MEMORY_READS:
            data = self.device.read_memory(address, size)
            if address == ADDR_HARDWARE_ID:
                hardware_id = data
            time.sleep(0.05)

        if len(hardware_id) != HARDWARE_ID_SIZE:
            raise ValueError(f"Failed to read the {HARDWARE_ID_SIZE}-byte HardwareID")

        response = self.device.streaming_auth(hardware_id)
        if response is None or len(response) < 4 or response[0] & 0x7F != 0x4C:
            raise ValueError("Invalid StreamingAuth response")
        result = struct.unpack("<H", response[2:4])[0]
        if result & 0x03 != 0x03:
            raise ValueError(f"StreamingAuth failed with result 0x{result:04X}")
        time.sleep(0.05)

        self.device.command(km003c.CMD_GET_DATA, WIRE_ATT_PD_PACKET)
        time.sleep(0.05)
        self.device.command(km003c.CMD_GET_DATA, WIRE_ATT_SETTINGS)
        time.sleep(0.05)

        print("Initialization complete")

    def get_log_metadata(self) -> list[LogMetadata]:
        """Request the offline log catalog (attribute 0x0200)."""
        response = self.device.command(km003c.CMD_GET_DATA, WIRE_ATT_LOG_METADATA)
        return [] if response is None else parse_catalog(response)

    def download_log_data(self, metadata: LogMetadata) -> bytes:
        """Download and decrypt raw offline log data with MemoryRead."""
        print(
            f"Requesting {metadata.data_size} bytes at 0x{metadata.data_address:08X}..."
        )
        return self.device.read_memory(
            metadata.data_address, metadata.data_size, timeout_ms=5000
        )


def print_summary(metadata: LogMetadata, samples: list[AdcSample]) -> None:
    print("\n=== Data Summary ===")
    voltages = [sample.voltage_v for sample in samples]
    currents = [sample.current_a for sample in samples]
    print(f"Voltage: {min(voltages):.3f}V - {max(voltages):.3f}V")
    print(f"Current: {min(currents):.3f}A - {max(currents):.3f}A")
    print(f"Final charge: {samples[-1].charge_mah:.3f} mAh")
    print(f"Final energy: {samples[-1].energy_mwh:.3f} mWh")

    header = f"{'#':>4} {'Voltage':>10} {'Current':>10} {'Charge':>12} {'Energy':>12}"
    print("\n=== First 5 Samples ===")
    print(header)
    for index, sample in enumerate(samples[:5]):
        print(
            f"{index:4} {sample.voltage_v:10.3f}V {sample.current_a:10.3f}A "
            f"{sample.charge_mah:10.3f}mAh {sample.energy_mwh:10.3f}mWh"
        )

    print("\n=== Last 5 Samples ===")
    for index, sample in enumerate(samples[-5:], start=max(len(samples) - 5, 0)):
        print(
            f"{index:4} {sample.voltage_v:10.3f}V {sample.current_a:10.3f}A "
            f"{sample.charge_mah:10.3f}mAh {sample.energy_mwh:10.3f}mWh"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download offline logs from POWER-Z KM003C"
    )
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("-r", "--raw", help="Output raw decrypted data to file")
    parser.add_argument(
        "-i", "--index", type=int, default=0, help="Zero-based catalog index"
    )
    args = parser.parse_args()

    try:
        with Km003cUsb("vendor") as device:
            downloader = OfflineLogDownloader(device)
            downloader.initialize()

            print("\nRequesting log metadata...")
            catalog = downloader.get_log_metadata()
            if not catalog:
                print("No log found on device")
                return 1

            print("\n=== Offline Log Catalog ===")
            for index, entry in enumerate(catalog):
                print(
                    f"[{index}] {entry.name}: {entry.sample_count} samples, "
                    f"address=0x{entry.data_address:08X}"
                )

            if not 0 <= args.index < len(catalog):
                raise ValueError(
                    f"Log index {args.index} is out of range; "
                    f"device reported {len(catalog)} logs"
                )
            metadata = catalog[args.index]

            print("\n=== Log Information ===")
            print(f"Name: {metadata.name}")
            print(f"Samples: {metadata.sample_count}")
            print(
                f"Interval: {metadata.interval_ms}ms ({metadata.interval_ms / 1000}s)"
            )
            duration = metadata.duration_seconds
            print(
                f"Duration: {int(duration // 3600)}:"
                f"{int((duration % 3600) // 60):02d}:{int(duration % 60):02d}"
            )
            if metadata.recorded_duration_seconds != duration:
                print(
                    "Warning: metadata duration differs from sample count: "
                    f"{metadata.recorded_duration_seconds}s"
                )
            print(f"Data size: {metadata.data_size} bytes")
            print(f"Data address: 0x{metadata.data_address:08X}")

            print("\n=== Downloading Log Data ===")
            data = downloader.download_log_data(metadata)

        samples = parse_samples(data)
        print(f"\nParsed {len(samples)} samples")
        if samples and (
            samples[-1].charge_acc_uah != metadata.final_charge_uah
            or samples[-1].energy_acc_uwh != metadata.final_energy_uwh
        ):
            raise ValueError("Downloaded data does not match metadata accumulators")

        print_summary(metadata, samples)

        if args.output:
            with open(args.output, "w") as handle:
                handle.write("sample,voltage_v,current_a,charge_mah,energy_mwh\n")
                for index, sample in enumerate(samples):
                    handle.write(
                        f"{index},{sample.voltage_v:.6f},{sample.current_a:.6f},"
                        f"{sample.charge_mah:.6f},{sample.energy_mwh:.6f}\n"
                    )
            print(f"\nSaved to {args.output}")

        if args.raw:
            with open(args.raw, "wb") as handle:
                handle.write(data)
            print(f"Raw data saved to {args.raw}")

        return 0

    except Exception as error:  # noqa: BLE001 - top-level CLI reporting
        print(f"\nError: {error}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
