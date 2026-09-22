"""Minimal pyusb transport shared by the hardware research scripts.

The scripts each carried their own copy of device discovery, kernel-driver
detachment, interface claiming and transaction-ID bookkeeping. Keeping one copy
here means a fix to the reset timing or the endpoint map applies everywhere.

This is deliberately thin: it does framing and transport only. Protocol
semantics live in :mod:`km003c_analysis.device.protocol` and in the Rust
`km003c` bindings.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import km003c
import usb.core
import usb.util

from . import protocol

__all__ = ["INTERFACES", "InterfaceConfig", "Km003cUsb", "MemoryReadError"]


class MemoryReadError(RuntimeError):
    """A MemoryRead request was rejected or answered incorrectly."""


@dataclass(frozen=True)
class InterfaceConfig:
    """One of the device's two usable protocol interfaces."""

    number: int
    endpoint_out: int
    endpoint_in: int
    description: str


INTERFACES: dict[str, InterfaceConfig] = {
    "vendor": InterfaceConfig(
        number=protocol.INTERFACE_VENDOR,
        endpoint_out=protocol.ENDPOINT_OUT_VENDOR,
        endpoint_in=protocol.ENDPOINT_IN_VENDOR,
        description="Vendor (Bulk, ~0.6ms latency, fastest)",
    ),
    "hid": InterfaceConfig(
        number=protocol.INTERFACE_HID,
        endpoint_out=protocol.ENDPOINT_OUT_HID,
        endpoint_in=protocol.ENDPOINT_IN_HID,
        description="HID (Interrupt, ~3.8ms latency, most compatible)",
    ),
}

# The device needs this long to re-enumerate after a USB reset; shorter waits
# were observed to leave AdcQueue streaming unavailable.
RESET_SETTLE_SECONDS = 1.5


class Km003cUsb:
    """A connected KM003C, addressed through one protocol interface."""

    def __init__(self, interface: str = "vendor", *, skip_reset: bool = False) -> None:
        try:
            self.config = INTERFACES[interface]
        except KeyError:
            raise ValueError(
                f"Unknown interface {interface!r}, expected one of {sorted(INTERFACES)}"
            ) from None

        device = self._find()
        if not skip_reset:
            try:
                device.reset()
                time.sleep(RESET_SETTLE_SECONDS)
            except usb.core.USBError:
                time.sleep(0.5)
            device = self._find()

        self.dev = device
        self._detach_kernel_drivers()
        self.dev.set_configuration()
        usb.util.claim_interface(self.dev, self.config.number)
        self.tid = 0

    @staticmethod
    def _find() -> Any:
        device = usb.core.find(idVendor=km003c.VID, idProduct=km003c.PID)
        if device is None:
            raise ValueError(
                f"POWER-Z KM003C not found (VID={km003c.VID:04x}, PID={km003c.PID:04x})"
            )
        return device

    def _detach_kernel_drivers(self) -> None:
        for cfg in self.dev:
            for interface in cfg:
                number = interface.bInterfaceNumber
                try:
                    if self.dev.is_kernel_driver_active(number):
                        self.dev.detach_kernel_driver(number)
                except (usb.core.USBError, NotImplementedError):
                    # Already detached, or the platform has no kernel drivers.
                    pass

    def close(self) -> None:
        usb.util.release_interface(self.dev, self.config.number)
        usb.util.dispose_resources(self.dev)

    def __enter__(self) -> Km003cUsb:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- framing ---------------------------------------------------------

    def next_tid(self) -> int:
        self.tid = (self.tid + 1) & 0xFF
        return self.tid

    def send(self, data: bytes) -> None:
        self.dev.write(self.config.endpoint_out, data)

    def receive(self, timeout_ms: int = 1000) -> bytes:
        return bytes(self.dev.read(self.config.endpoint_in, 4096, timeout=timeout_ms))

    def command(
        self, packet_type: int, attribute: int, timeout_ms: int = 1000
    ) -> bytes | None:
        """Send a 4-byte control command and return its raw response."""
        packet = km003c.create_packet(packet_type, self.next_tid(), attribute)
        self.send(packet)
        try:
            return self.receive(timeout_ms)
        except usb.core.USBTimeoutError:
            return None

    def connect(self) -> bytes | None:
        """Send the Connect (0x02) command that precedes authenticated reads."""
        return self.command(km003c.CMD_CONNECT, 0)

    # -- authenticated commands -----------------------------------------

    def read_memory(self, address: int, size: int, timeout_ms: int = 1000) -> bytes:
        """Read and decrypt `size` bytes of device memory.

        Raises:
            MemoryReadError: If the device rejects the address or answers with
                a confirmation that does not match the request.
        """
        transaction_id = self.next_tid()
        self.send(protocol.build_memory_read_packet(address, size, transaction_id))

        try:
            confirmation = self.receive(timeout_ms)
        except usb.core.USBTimeoutError as error:
            raise MemoryReadError(f"No confirmation for 0x{address:08X}") from error

        if len(confirmation) < 4:
            raise MemoryReadError(
                f"Short confirmation for 0x{address:08X}: {len(confirmation)} bytes"
            )

        response_type = confirmation[0] & 0x7F
        if response_type == km003c.CMD_REJECT:
            raise MemoryReadError(f"MemoryRead at 0x{address:08X} was rejected")
        if response_type == protocol.CMD_NOT_READABLE:
            raise MemoryReadError(f"Memory address 0x{address:08X} is not readable")
        if response_type != protocol.CMD_MEMORY_READ:
            raise MemoryReadError(
                f"Unexpected response type 0x{response_type:02X} for 0x{address:08X}"
            )
        if confirmation[1] != transaction_id:
            raise MemoryReadError(
                "MemoryRead confirmation has the wrong transaction ID"
            )

        echoed = protocol.parse_memory_read_confirmation(confirmation)
        if echoed != (address, size):
            raise MemoryReadError(
                f"MemoryRead confirmation echoed {echoed}, expected ({address}, {size})"
            )

        expected = protocol.aligned_response_size(size)
        encrypted = bytearray()
        while len(encrypted) < expected:
            try:
                transfer = self.receive(timeout_ms)
            except usb.core.USBTimeoutError as error:
                raise MemoryReadError(f"Truncated data for 0x{address:08X}") from error
            if not transfer or len(encrypted) + len(transfer) > expected:
                raise MemoryReadError(f"Invalid data length for 0x{address:08X}")
            encrypted.extend(transfer)

        return protocol.decrypt_memory_payload(bytes(encrypted))[:size]

    def hardware_id(self) -> bytes:
        """Read the 12-byte HardwareID used for level-1 authentication."""
        return self.read_memory(protocol.ADDR_HARDWARE_ID, protocol.HARDWARE_ID_SIZE)

    def streaming_auth(self, credential: bytes, timeout_ms: int = 1000) -> bytes | None:
        """Authenticate with a 12-byte credential and return the raw response."""
        self.send(protocol.build_streaming_auth_packet(credential, self.next_tid()))
        try:
            return self.receive(timeout_ms)
        except usb.core.USBTimeoutError:
            return None
