"""
Integration tests for KM003C device communication.

These tests require a real KM003C device connected via USB.
They validate the protocol implementation and test the km003c_lib Rust bindings.

Run with: pytest -m integration -v -s
Or: pytest tests/integration/ -v -s
"""

import sys
import time
from pathlib import Path

import pytest
import usb.core
import usb.util
from km003c import (
    ATT_ADC,
    ATT_ADC_QUEUE,
    CMD_CONNECT,
    CMD_GET_DATA,
    CMD_START_GRAPH,
    CMD_STOP_GRAPH,
    PID,
    RATE_50_SPS,
    VID,
    AdcData,
    create_packet,
    parse_packet,
    parse_raw_packet,
)

# Import helpers for dict-based API navigation
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from km003c_helpers import get_adc_data, get_adcqueue_data, get_packet_type
from run_adcqueue_single import (
    HARDWARE_ID_ADDRESS,
    build_memory_read_request,
    build_streaming_auth_request,
    decrypt_hardware_id,
    validate_memory_read_confirmation,
)

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def device():
    """
    Device fixture - sets up and tears down USB connection.

    Yields a dictionary with device handle and communication functions.
    """
    # Find device
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        pytest.skip("KM003C device not connected")

    # Reset and initialize
    try:
        dev.reset()
        time.sleep(1.5)  # Wait for device to fully initialize
    except Exception as e:
        pytest.skip(f"Could not reset device: {e}")

    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        pytest.skip("Device not found after reset")

    # Detach kernel drivers
    interface_num = 0  # Use Interface 0 (Bulk, fastest)
    endpoint_out = 0x01
    endpoint_in = 0x81

    for cfg in dev:
        for intf in cfg:
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                dev.detach_kernel_driver(intf.bInterfaceNumber)

    dev.set_configuration()
    usb.util.claim_interface(dev, interface_num)

    # Helper functions
    tid_counter = [0]  # Use list for mutability in closure

    def next_tid():
        tid = tid_counter[0]
        tid_counter[0] = (tid + 1) & 0xFF
        return tid

    def send_command(cmd_type, data_word):
        """Send command using km003c_lib packet creation."""
        tid = next_tid()

        # Use km003c_lib to create packet (no manual bit manipulation!)
        packet = create_packet(cmd_type, tid, data_word)

        dev.write(endpoint_out, packet)
        try:
            response = bytes(dev.read(endpoint_in, 4096, timeout=2000))
            return tid, response
        except Exception:
            return tid, None

    def reset_device_state():
        """Reset device to known state (minimal)."""
        # Connect
        send_command(CMD_CONNECT, 0)
        time.sleep(0.05)
        # Ensure not in graph mode
        send_command(CMD_STOP_GRAPH, 0)
        time.sleep(0.1)

    def full_device_init():
        """Authenticate the connected device for AdcQueue streaming."""
        # Connect
        send_command(CMD_CONNECT, 0)
        time.sleep(0.05)

        # Read this device's HardwareID. The second response is raw ciphertext.
        memory_tid = next_tid()
        memory_request = build_memory_read_request(HARDWARE_ID_ADDRESS, 12, memory_tid)
        dev.write(endpoint_out, memory_request)
        confirmation = bytes(dev.read(endpoint_in, 2048, timeout=2000))
        validate_memory_read_confirmation(
            confirmation, memory_tid, HARDWARE_ID_ADDRESS, 12
        )
        ciphertext = bytes(dev.read(endpoint_in, 2048, timeout=2000))
        hardware_id = decrypt_hardware_id(ciphertext)

        # Generate a fresh request rather than replaying device-specific capture data.
        auth_tid = next_tid()
        dev.write(endpoint_out, build_streaming_auth_request(hardware_id, auth_tid))
        auth_response = bytes(dev.read(endpoint_in, 2048, timeout=2000))
        if auth_response[:4] != bytes.fromhex("4c000302"):
            raise ValueError(f"StreamingAuth failed: {auth_response.hex()}")

    # Initial cleanup
    reset_device_state()

    yield {
        "dev": dev,
        "send_command": send_command,
        "reset_state": reset_device_state,
        "full_init": full_device_init,
        "endpoint_out": endpoint_out,
        "endpoint_in": endpoint_in,
    }

    # Cleanup - ensure device not in graph mode
    try:
        send_command(CMD_STOP_GRAPH, 0)
        time.sleep(0.1)
    except usb.core.USBError:
        pass

    usb.util.release_interface(dev, interface_num)
    try:
        dev.reset()
    except usb.core.USBError:
        pass
    usb.util.dispose_resources(dev)


class TestBasicCommunication:
    """Test basic device communication and protocol parsing."""

    def test_device_found(self):
        """Verify device can be found via USB."""
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        assert dev is not None, "KM003C device not found"

    def test_connect_command(self, device):
        """Test Connect command."""
        tid, response = device["send_command"](CMD_CONNECT, 0)

        assert response is not None, "No response to Connect command"
        assert len(response) == 4, f"Expected 4 bytes, got {len(response)}"

        # Parse response with km003c_lib
        packet = parse_packet(response)
        assert get_packet_type(packet) == "Accept", (
            f"Expected Accept, got {get_packet_type(packet)}"
        )

    def test_get_adc_data(self, device):
        """Test requesting ADC data."""
        # Request ADC data using library constants
        tid, response = device["send_command"](CMD_GET_DATA, ATT_ADC)

        assert response is not None, "No response to GetData ADC"
        assert len(response) == 52, f"Expected 52 bytes for ADC, got {len(response)}"

        # Parse with km003c_lib
        packet = parse_packet(response)

        assert get_packet_type(packet) == "DataResponse", (
            f"Expected DataResponse, got {get_packet_type(packet)}"
        )
        adc = get_adc_data(packet)
        assert adc is not None, "No ADC data in response"
        assert isinstance(adc.vbus_v, float), "VBUS not a float"
        assert isinstance(adc.ibus_a, float), "IBUS not a float"
        assert isinstance(adc.power_w, float), "Power not a float"
        assert isinstance(adc.temp_c, float), "Temperature not a float"

        # Sanity checks
        assert -1.0 <= adc.vbus_v <= 50.0, f"VBUS out of range: {adc.vbus_v}V"
        assert -10.0 <= adc.ibus_a <= 10.0, f"IBUS out of range: {adc.ibus_a}A"
        assert -50.0 <= adc.temp_c <= 100.0, f"Temperature out of range: {adc.temp_c}°C"


class TestAdcQueueStreaming:
    """Test AdcQueue multi-sample streaming mode."""

    def test_start_graph_accepted(self, device):
        """Test that Start Graph command is accepted."""
        device["reset_state"]()

        # Start Graph at 50 SPS using library constants
        tid, response = device["send_command"](CMD_START_GRAPH, RATE_50_SPS)

        assert response is not None, "No response to Start Graph"

        # Parse response with km003c_lib
        packet = parse_packet(response)
        assert get_packet_type(packet) == "Accept", (
            f"Start Graph rejected: got {get_packet_type(packet)}"
        )

        # Cleanup
        device["send_command"](CMD_STOP_GRAPH, 0)
        time.sleep(0.1)

    def test_adcqueue_data_streaming(self, device):
        """Test authenticated AdcQueue streaming from start through stop."""
        device["full_init"]()  # Full init required for AdcQueue

        # Start Graph at 50 SPS using library
        tid, response = device["send_command"](CMD_START_GRAPH, RATE_50_SPS)
        packet = parse_packet(response)
        assert get_packet_type(packet) == "Accept", "Start Graph not accepted"

        # Wait for samples to accumulate
        time.sleep(2.0)  # 2 seconds = ~100 samples at 50 SPS

        # Request AdcQueue data. A complete response can exceed 1024 bytes.
        adcqueue_success = False
        for attempt in range(5):
            tid, response = device["send_command"](CMD_GET_DATA, ATT_ADC_QUEUE)

            if not response:
                continue

            # Parse with km003c_lib (now supports AdcQueue!)
            try:
                packet = parse_packet(response)
                adcq = get_adcqueue_data(packet)

                if adcq:
                    samples = adcq.samples
                    assert len(samples) > 0, "AdcQueue data has no samples"
                    assert len(samples) >= 5, (
                        f"Expected >=5 samples, got {len(samples)}"
                    )

                    # Validate sample data
                    first = samples[0]
                    assert isinstance(first.sequence, int)
                    assert isinstance(first.vbus_v, float)
                    assert -1.0 <= first.vbus_v <= 50.0, (
                        f"VBUS out of range: {first.vbus_v}V"
                    )

                    print(f"✓ AdcQueue working: {len(samples)} samples, first={first}")
                    adcqueue_success = True
                    break
                elif get_adc_data(packet):
                    print(
                        f"  Attempt {attempt + 1}: Got ADC data (single sample), retrying..."
                    )
                else:
                    # Debug: show what we got
                    debug_info = f"type={get_packet_type(packet)}"
                    print(
                        f"  Attempt {attempt + 1}: Got unexpected: {debug_info}, retrying..."
                    )
            except Exception as e:
                print(f"  Attempt {attempt + 1}: Parse error: {e}")

            time.sleep(0.2)

        assert adcqueue_success, "Failed to get AdcQueue data after 5 attempts"

        # Stop Graph
        tid, response = device["send_command"](CMD_STOP_GRAPH, 0)
        packet = parse_packet(response)
        assert get_packet_type(packet) == "Accept", (
            f"Stop Graph returned {response.hex()}: {packet}"
        )


class TestRustLibraryBindings:
    """Test km003c_lib Python bindings."""

    def test_parse_adc_response(self, device):
        """Test that parse_packet correctly parses ADC responses."""
        tid, response = device["send_command"](CMD_GET_DATA, ATT_ADC)

        packet = parse_packet(response)
        assert get_packet_type(packet) == "DataResponse"
        adc = get_adc_data(packet)
        assert adc is not None

        # ADC data should be an AdcData instance
        assert isinstance(adc, AdcData)
        assert isinstance(adc.vbus_v, float)

    def test_parse_raw_packet(self, device):
        """Test parse_raw_packet exposes protocol details."""
        tid, response = device["send_command"](CMD_GET_DATA, ATT_ADC)

        raw = parse_raw_packet(response)

        # RawPacket is a dict with variant key ("Data", "Ctrl", or "SimpleData")
        assert isinstance(raw, dict)
        assert "Data" in raw, f"Expected Data variant, got {list(raw.keys())}"
        header = raw["Data"]["header"]
        lps = raw["Data"]["logical_packets"]
        assert header["packet_type"] == 0x41  # PutData
        assert header["id"] == tid
        assert len(lps) > 0
        assert lps[0]["attribute"] == 1  # ATT_ADC
        assert lps[0]["next"] is False
        assert lps[0]["size"] == 44  # ADC payload size

    def test_packet_creation(self):
        """Test that create_packet generates correct bytes."""
        # Test various packet types
        connect_pkt = create_packet(CMD_CONNECT, 1, 0)
        assert connect_pkt == bytes([0x02, 0x01, 0x00, 0x00])

        getdata_pkt = create_packet(CMD_GET_DATA, 2, ATT_ADC)
        assert getdata_pkt == bytes([0x0C, 0x02, 0x02, 0x00])

        start_graph_pkt = create_packet(CMD_START_GRAPH, 3, RATE_50_SPS)
        assert start_graph_pkt == bytes([0x0E, 0x03, 0x04, 0x00])
