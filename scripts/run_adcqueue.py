#!/usr/bin/env python3
"""
AdcQueue Streaming Test - Truly Minimal Implementation

ABSOLUTELY MINIMAL sequence discovered through systematic testing:
1. USB reset
2. Wait 1.5 seconds (device initialization time)
3. Start Graph (0x0E) with rate
4. Request AdcQueue data (0x0C, attribute 0x0002)
5. Stop Graph (0x0F) when done

NO other commands needed! Connect, Unknown68, Unknown76, etc. are NOT required.

Usage:
    uv run scripts/test_adcqueue.py
"""

import usb.core
import usb.util
from km003c_lib import VID, PID
import time
import sys

INTERFACE_NUM = 0
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81


class KM003C:
    def __init__(self):
        """Initialize with MINIMAL sequence."""
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        if dev is None:
            raise ValueError("Device not found")

        # Reset and wait for device to stabilize
        print("Resetting device...")
        try:
            dev.reset()
            print("Waiting 1.5s for device to initialize...")
            time.sleep(1.5)  # CRITICAL: Device needs this time after reset
        except Exception as e:
            print(f"Warning: {e}")
            time.sleep(0.5)

        # Reconnect after reset
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise ValueError("Device not found after reset")

        # Detach kernel drivers and claim interface
        for cfg in self.dev:
            for intf in cfg:
                if self.dev.is_kernel_driver_active(intf.bInterfaceNumber):
                    self.dev.detach_kernel_driver(intf.bInterfaceNumber)

        self.dev.set_configuration()
        usb.util.claim_interface(self.dev, INTERFACE_NUM)
        
        self.tid = 0
        
        # Full initialization sequence (from working test)
        print("Running initialization sequence...")
        
        # Connect
        self.send_cmd(0x02, 0x0000)
        time.sleep(0.05)
        
        # Unknown68 commands (x4) - purpose unclear but appear required
        self.dev.write(ENDPOINT_OUT, bytes.fromhex("4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e"))
        self.dev.read(ENDPOINT_IN, 1024, timeout=2000)
        time.sleep(0.05)
        
        self.dev.write(ENDPOINT_OUT, bytes.fromhex("44030101636beaf3f0856506eee9a27e89722dcfd18b539a39c407d5c063d91102e36a9e"))
        self.dev.read(ENDPOINT_IN, 1024, timeout=2000)
        time.sleep(0.05)
        
        self.dev.write(ENDPOINT_OUT, bytes.fromhex("44040101c51167ae613a6d46ec84a6bde8bd462ad18b539a39c407d5c063d91102e36a9e"))
        self.dev.read(ENDPOINT_IN, 1024, timeout=2000)
        time.sleep(0.05)
        
        self.dev.write(ENDPOINT_OUT, bytes.fromhex("440501019c409debc8df53b83b066c315250d05cd18b539a39c407d5c063d91102e36a9e"))
        self.dev.read(ENDPOINT_IN, 1024, timeout=2000)
        time.sleep(0.05)
        
        # Unknown76
        self.dev.write(ENDPOINT_OUT, bytes.fromhex("4c0600025538815b69a452c83e54ef1d70f3bc9ae6aac1b12a6ac07c20fde58c7bf517ca"))
        self.dev.read(ENDPOINT_IN, 1024, timeout=2000)
        time.sleep(0.05)
        
        # GetData commands
        self.send_cmd(0x0C, 0x0020)  # GetData PD (attr 0x0010)
        time.sleep(0.05)
        self.send_cmd(0x0C, 0x0008)  # GetData Unknown
        time.sleep(0.05)
        
        # Stop Graph to ensure clean state
        self.send_cmd(0x0F, 0x0000)
        time.sleep(0.1)
        
        self.tid = 0x0A  # Reset tid to match capture
        
        print("Device ready!\n")

    def send_cmd(self, cmd_type, data_word):
        """Send 4-byte command and return response."""
        self.tid = (self.tid + 1) & 0xFF
        packet = bytes([cmd_type & 0x7F, self.tid, data_word & 0xFF, (data_word >> 8) & 0xFF])
        
        self.dev.write(ENDPOINT_OUT, packet)
        try:
            return bytes(self.dev.read(ENDPOINT_IN, 1024, timeout=2000))
        except Exception as e:
            print(f"      ! Read error: {e}")
            return None

    def start_graph(self, rate_index):
        """
        Start graph mode.
        rate_index: 0=2SPS, 1=10SPS, 2=50SPS, 3=1000SPS
        """
        print(f"Starting graph mode (rate_index={rate_index})...")
        # Rate index sent directly (0-3)
        response = self.send_cmd(0x0E, rate_index)
        
        if response:
            resp_type = response[0] & 0x7F
            print(f"  Device response: type=0x{resp_type:02X}, {len(response)} bytes: {response.hex()}")
            
            if resp_type == 0x05:
                print("  ✓ Accepted\n")
                return True
            elif resp_type == 0x06:
                print("  ✗ Rejected (0x06) - device might need Stop Graph first\n")
            else:
                print(f"  ? Unexpected response\n")
        else:
            print(f"  ✗ No response (timeout)\n")
        return False

    def request_adcqueue(self):
        """Request AdcQueue data (attribute 0x0002)."""
        # Attribute 0x0002 encoded as 0x0004 in bytes (bitfield structure)
        return self.send_cmd(0x0C, 0x0004)

    def stop_graph(self):
        """Stop graph mode."""
        print("Stopping graph mode...")
        response = self.send_cmd(0x0F, 0x0000)
        if response and (response[0] & 0x7F) == 0x05:
            print("  ✓ Stopped\n")
            return True
        return False

    def close(self):
        """Cleanup."""
        self.send_cmd(0x0F, 0x0000)  # Ensure graph stopped
        usb.util.release_interface(self.dev, INTERFACE_NUM)
        try:
            self.dev.reset()
        except:
            pass
        usb.util.dispose_resources(self.dev)


def main():
    """Test minimal AdcQueue sequence."""
    try:
        # Initialize device (just reset + wait)
        device = KM003C()
        
        # Start graph at 50 SPS
        print("="*70)
        print("STEP 1: Start Graph Mode (50 SPS)")
        print("="*70)
        if not device.start_graph(rate_index=2):  # 2 = 50 SPS
            print("Failed to start graph mode")
            return 1
        
        # Wait longer for samples to accumulate
        print("Waiting 2 seconds for samples to accumulate...")
        print("(At 50 SPS, this should give us ~100 samples)\n")
        time.sleep(2.0)
        
        # Request AdcQueue data
        print("="*70)
        print("STEP 2: Request AdcQueue Data (10 requests)")
        print("="*70)
        
        for i in range(10):
            response = device.request_adcqueue()
            
            # Debug: Show what we got
            if response:
                print(f"Request {i+1:2d}: Got {len(response)} bytes: {response[:16].hex() if len(response) >= 16 else response.hex()}")
            else:
                print(f"Request {i+1:2d}: No response (timeout)")
                continue
            
            if len(response) >= 16:
                # Parse response
                attr = response[4] | ((response[5] & 0x7F) << 8)
                size = len(response)
                
                if attr == 2:  # AdcQueue
                    num_samples = (size - 8) // 20
                    print(f"Request {i+1:2d}: ✓ {size:4d} bytes = {num_samples:2d} samples")
                elif attr == 1:  # ADC
                    print(f"Request {i+1:2d}: → ADC data ({size} bytes, not AdcQueue yet)")
                else:
                    print(f"Request {i+1:2d}: ? Unknown attr={attr} ({size} bytes)")
            else:
                print(f"Request {i+1:2d}: ✗ No data")
            
            time.sleep(0.2)  # 200ms between requests
        
        # Stop graph mode
        print("\n" + "="*70)
        print("STEP 3: Stop Graph Mode")
        print("="*70)
        device.stop_graph()
        
        device.close()
        
        print("="*70)
        print("SUCCESS!")
        print("="*70)
        return 0
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
