"""
Integration tests for KM003C device communication.

These tests require a real KM003C device connected via USB.
They validate the protocol implementation and test the km003c_lib Rust bindings.

Run with: pytest -m integration -v -s
Or: pytest tests/integration/ -v -s
"""

import pytest
import usb.core
import usb.util
import time
from km003c_lib import (
    VID, PID,
    parse_packet, parse_raw_packet,
    create_packet,
    CMD_CONNECT, CMD_GET_DATA, CMD_START_GRAPH, CMD_STOP_GRAPH,
    ATT_ADC, ATT_ADC_QUEUE,
    RATE_50_SPS,
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
    
    def send_command(cmd_type, data_word):
        """Send command using km003c_lib packet creation."""
        tid = tid_counter[0]
        tid_counter[0] = (tid_counter[0] + 1) & 0xFF
        
        # Use km003c_lib to create packet (no manual bit manipulation!)
        packet = create_packet(cmd_type, tid, data_word)
        
        dev.write(endpoint_out, packet)
        try:
            response = bytes(dev.read(endpoint_in, 1024, timeout=2000))
            return tid, response
        except Exception as e:
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
        """
        Full device initialization sequence from captures.
        
        Required for some features (AdcQueue) to work properly after fresh reset.
        Purpose of Unknown68/Unknown76 commands not yet understood.
        """
        # Connect
        send_command(CMD_CONNECT, 0)
        time.sleep(0.05)
        
        # Unknown68 commands (x4) - purpose unclear, hardcoded from capture
        # TODO: Understand what these commands do
        for cmd_hex in [
            "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e",
            "44030101636beaf3f0856506eee9a27e89722dcfd18b539a39c407d5c063d91102e36a9e",
            "44040101c51167ae613a6d46ec84a6bde8bd462ad18b539a39c407d5c063d91102e36a9e",
            "440501019c409debc8df53b83b066c315250d05cd18b539a39c407d5c063d91102e36a9e",
        ]:
            dev.write(endpoint_out, bytes.fromhex(cmd_hex))
            try:
                dev.read(endpoint_in, 1024, timeout=2000)
            except:
                pass
            time.sleep(0.05)
        
        # Unknown76 - purpose unclear, hardcoded from capture
        dev.write(endpoint_out, bytes.fromhex("4c0600025538815b69a452c83e54ef1d70f3bc9ae6aac1b12a6ac07c20fde58c7bf517ca"))
        try:
            dev.read(endpoint_in, 1024, timeout=2000)
        except:
            pass
        time.sleep(0.05)
        
        # GetData PD and Unknown
        send_command(CMD_GET_DATA, 0x0010)  # PD attribute
        time.sleep(0.05)
        send_command(CMD_GET_DATA, 0x0004)  # Unknown attribute
        time.sleep(0.05)
        
        # Stop Graph
        send_command(CMD_STOP_GRAPH, 0)
        time.sleep(0.1)
        
        # Flush any remaining buffered responses
        try:
            while True:
                dev.read(endpoint_in, 1024, timeout=100)
        except:
            pass  # Timeout means no more data
    
    # Initial cleanup
    reset_device_state()
    
    yield {
        'dev': dev,
        'send_command': send_command,
        'reset_state': reset_device_state,
        'full_init': full_device_init,
        'endpoint_out': endpoint_out,
        'endpoint_in': endpoint_in,
    }
    
    # Cleanup - ensure device not in graph mode
    try:
        send_command(CMD_STOP_GRAPH, 0)
        time.sleep(0.1)
    except:
        pass
    
    usb.util.release_interface(dev, interface_num)
    try:
        dev.reset()
    except:
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
        tid, response = device['send_command'](CMD_CONNECT, 0)
        
        assert response is not None, "No response to Connect command"
        assert len(response) == 4, f"Expected 4 bytes, got {len(response)}"
        
        # Parse response with km003c_lib
        packet = parse_packet(response)
        assert packet.packet_type == "Accept", f"Expected Accept, got {packet.packet_type}"
    
    def test_get_adc_data(self, device):
        """Test requesting ADC data."""
        # Request ADC data using library constants
        tid, response = device['send_command'](CMD_GET_DATA, ATT_ADC)
        
        assert response is not None, "No response to GetData ADC"
        assert len(response) == 52, f"Expected 52 bytes for ADC, got {len(response)}"
        
        # Parse with km003c_lib
        packet = parse_packet(response)
        
        assert packet.packet_type == "DataResponse", f"Expected DataResponse, got {packet.packet_type}"
        assert packet.adc_data is not None, "No ADC data in response"
        
        # Validate ADC data fields
        adc = packet.adc_data
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
        device['reset_state']()
        
        # Start Graph at 50 SPS using library constants
        tid, response = device['send_command'](CMD_START_GRAPH, RATE_50_SPS)
        
        assert response is not None, "No response to Start Graph"
        
        # Parse response with km003c_lib
        packet = parse_packet(response)
        assert packet.packet_type == "Accept", f"Start Graph rejected: got {packet.packet_type}"
        
        # Cleanup
        device['send_command'](CMD_STOP_GRAPH, 0)
        time.sleep(0.1)
    
    @pytest.mark.xfail(reason="AdcQueue test has device state issues in pytest fixtures. Use scripts/test_adcqueue.py for validation.")
    def test_adcqueue_data_streaming(self, device):
        """
        Test full AdcQueue streaming: start, request data, stop.
        
        Note: AdcQueue requires full device initialization and complex state management
        that doesn't work reliably in pytest fixture context (device returns buffered
        responses from previous commands, attribute 512, etc.).
        
        For reliable AdcQueue testing, use: uv run scripts/test_adcqueue.py
        """
        device['full_init']()  # Full init required for AdcQueue
        
        # Start Graph at 50 SPS using library
        tid, response = device['send_command'](CMD_START_GRAPH, RATE_50_SPS)
        packet = parse_packet(response)
        assert packet.packet_type == "Accept", "Start Graph not accepted"
        
        # Wait for samples to accumulate
        time.sleep(2.0)  # 2 seconds = ~100 samples at 50 SPS
        
        # Request AdcQueue data multiple times (first request might return other data)
        adcqueue_success = False
        for attempt in range(5):
            tid, response = device['send_command'](CMD_GET_DATA, ATT_ADC_QUEUE)
            
            if not response:
                continue
            
            # Parse with km003c_lib (now supports AdcQueue!)
            try:
                packet = parse_packet(response)
                
                if packet.adcqueue_data:
                    samples = packet.adcqueue_data.samples
                    assert len(samples) > 0, "AdcQueue data has no samples"
                    assert len(samples) >= 5, f"Expected >=5 samples, got {len(samples)}"
                    
                    # Validate sample data
                    first = samples[0]
                    assert isinstance(first.sequence, int)
                    assert isinstance(first.vbus_v, float)
                    assert -1.0 <= first.vbus_v <= 50.0, f"VBUS out of range: {first.vbus_v}V"
                    
                    print(f"✓ AdcQueue working: {len(samples)} samples, first={first}")
                    adcqueue_success = True
                    break
                elif packet.adc_data:
                    print(f"  Attempt {attempt+1}: Got ADC data (single sample), retrying...")
                else:
                    # Debug: show what we got
                    debug_info = f"type={packet.packet_type}"
                    if packet.raw_payload:
                        debug_info += f", raw={len(packet.raw_payload)} bytes"
                    print(f"  Attempt {attempt+1}: Got unexpected: {debug_info}, retrying...")
            except Exception as e:
                print(f"  Attempt {attempt+1}: Parse error: {e}")
            
            time.sleep(0.2)
        
        assert adcqueue_success, "Failed to get AdcQueue data after 5 attempts"
        
        # Stop Graph
        tid, response = device['send_command'](CMD_STOP_GRAPH, 0)
        packet = parse_packet(response)
        assert packet.packet_type == "Accept", "Stop Graph not accepted"


class TestRustLibraryBindings:
    """Test km003c_lib Python bindings."""
    
    def test_parse_adc_response(self, device):
        """Test that parse_packet correctly parses ADC responses."""
        tid, response = device['send_command'](CMD_GET_DATA, ATT_ADC)
        
        packet = parse_packet(response)
        assert packet.packet_type == "DataResponse"
        assert packet.adc_data is not None
        
        # Test repr
        repr_str = repr(packet)
        assert "AdcData" in repr_str
    
    def test_parse_raw_packet(self, device):
        """Test parse_raw_packet exposes protocol details."""
        tid, response = device['send_command'](CMD_GET_DATA, ATT_ADC)
        
        raw = parse_raw_packet(response)
        
        # Check protocol fields
        assert raw.packet_type == "PutData"
        assert raw.packet_type_id == 0x41
        assert raw.id == tid
        assert raw.has_extended_header == True
        assert raw.ext_attribute_id == 1  # ATT_ADC
        assert raw.ext_next == False
        assert raw.ext_size == 44  # ADC payload size
    
    def test_packet_creation(self):
        """Test that create_packet generates correct bytes."""
        # Test various packet types
        connect_pkt = create_packet(CMD_CONNECT, 1, 0)
        assert connect_pkt == bytes([0x02, 0x01, 0x00, 0x00])
        
        getdata_pkt = create_packet(CMD_GET_DATA, 2, ATT_ADC)
        assert getdata_pkt == bytes([0x0C, 0x02, 0x02, 0x00])
        
        start_graph_pkt = create_packet(CMD_START_GRAPH, 3, RATE_50_SPS)
        assert start_graph_pkt == bytes([0x0E, 0x03, 0x04, 0x00])
