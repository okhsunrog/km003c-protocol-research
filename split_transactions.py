#!/usr/bin/env python3
"""
USB Transaction Splitter for KM003C Protocol Analysis

This script splits USB capture frames into logical transactions following the KM003C
protocol patterns as documented in transaction_splitting_guide.md.

The script handles:
1. Control transfers (transfer_type "0x02") - complete control transfer sequences
2. Bulk transfers (transfer_type "0x03") - KM003C command-response patterns

Key patterns:
- Control: S → [data stages] → C (all with same urb_id)
- KM003C Bulk: S(cmd,0x01) → C(ack,0x01) → C(data,0x81) → S(pre-pos,0x81)
"""

import json
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Frame:
    """Represents a single USB frame"""
    frame_number: int
    timestamp: float
    transfer_type: str
    endpoint_address: str
    urb_type: str
    urb_status: str
    urb_id: str
    payload_hex: str
    data_length: int
    raw_data: Dict[str, Any]
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'Frame':
        """Create Frame from JSON data"""
        return cls(
            frame_number=data.get('frame_number', 0),
            timestamp=data.get('timestamp', 0.0),
            transfer_type=data.get('transfer_type', ''),
            endpoint_address=data.get('endpoint_address', ''),
            urb_type=data.get('urb_type', ''),
            urb_status=data.get('urb_status', ''),
            urb_id=data.get('urb_id', ''),
            payload_hex=data.get('payload_hex', ''),
            data_length=data.get('data_length', 0),
            raw_data=data
        )


@dataclass
class Transaction:
    """Represents a logical USB transaction"""
    transaction_id: str
    transaction_type: str
    frames: List[Frame]
    start_time: float
    duration: float
    description: str


class KM003CTransactionSplitter:
    """Splits USB frames into KM003C protocol transactions"""
    
    def __init__(self):
        self.transactions: List[Transaction] = []
        self.frame_index = 0
    
    def load_frames(self, filename: str) -> List[Frame]:
        """Load frames from JSONL file"""
        frames = []
        with open(filename, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    data = json.loads(line)
                    frames.append(Frame.from_json(data))
                except json.JSONDecodeError as e:
                    print(f"Warning: Skipping invalid JSON on line {line_num}: {e}")
                except Exception as e:
                    print(f"Warning: Error processing line {line_num}: {e}")
        return frames
    
    def is_control_transfer(self, frame: Frame) -> bool:
        """Check if frame is a control transfer"""
        return frame.transfer_type == "0x02"
    
    def is_bulk_transfer(self, frame: Frame) -> bool:
        """Check if frame is a bulk transfer"""
        return frame.transfer_type == "0x03"
    
    def is_km003c_command(self, frame: Frame) -> bool:
        """Check if frame is a KM003C command (bulk transfer to 0x01 with payload)"""
        return (self.is_bulk_transfer(frame) and 
                frame.endpoint_address == "0x01" and 
                frame.urb_type == "S" and 
                frame.data_length > 0)
    
    def is_km003c_setup_buffer(self, frame: Frame) -> bool:
        """Check if frame is setting up a receive buffer (bulk S to 0x81 with no payload)"""
        return (self.is_bulk_transfer(frame) and 
                frame.endpoint_address == "0x81" and 
                frame.urb_type == "S" and 
                frame.data_length == 0)
    
    def extract_command_id(self, payload_hex: str) -> Optional[str]:
        """Extract command ID from KM003C payload"""
        if len(payload_hex) >= 4:
            # KM003C commands typically have format: 0c[ID]0200
            if payload_hex.startswith('0c') and payload_hex.endswith('0200'):
                return payload_hex[2:4]
        return None
    
    def get_time_gap(self, frame1: Frame, frame2: Frame) -> float:
        """Calculate time gap between two frames in seconds"""
        return frame2.timestamp - frame1.timestamp
    
    def collect_control_transfer(self, frames: List[Frame], start_idx: int) -> List[Frame]:
        """Collect all frames that belong to a control transfer"""
        if start_idx >= len(frames):
            return []
        
        start_frame = frames[start_idx]
        if not (self.is_control_transfer(start_frame) and start_frame.urb_type == "S"):
            return []
        
        transaction_frames = [start_frame]
        urb_id = start_frame.urb_id
        
        # Collect all subsequent frames with same URB ID
        for i in range(start_idx + 1, len(frames)):
            frame = frames[i]
            if frame.urb_id == urb_id and self.is_control_transfer(frame):
                transaction_frames.append(frame)
                # Stop after the Complete
                if frame.urb_type == "C":
                    break
            else:
                # Different URB ID or transfer type - end of transaction
                break
        
        return transaction_frames
    
    def collect_km003c_transaction(self, frames: List[Frame], start_idx: int) -> List[Frame]:
        """Collect frames for a KM003C command-response transaction"""
        if start_idx >= len(frames):
            return []
        
        start_frame = frames[start_idx]
        if not self.is_km003c_command(start_frame):
            return []
        
        transaction_frames = [start_frame]
        
        # Look for the 4-frame pattern: S(cmd,0x01) → C(ack,0x01) → C(data,0x81) → S(pre-pos,0x81)
        i = start_idx + 1
        
        # Step 1: Find ACK (C on 0x01 with same URB ID)
        if i < len(frames):
            frame = frames[i]
            if (frame.urb_id == start_frame.urb_id and 
                frame.endpoint_address == "0x01" and 
                frame.urb_type == "C"):
                transaction_frames.append(frame)
                i += 1
        
        # Step 2: Find data response (C on 0x81)
        # This will have a different URB ID (from previous pre-positioned buffer)
        if i < len(frames):
            frame = frames[i]
            if (frame.endpoint_address == "0x81" and 
                frame.urb_type == "C" and
                frame.data_length > 0):
                transaction_frames.append(frame)
                i += 1
        
        # Step 3: Find pre-position submit (S on 0x81 with no payload)
        # This should happen quickly after the data response (< 2ms typically)
        if i < len(frames):
            frame = frames[i]
            if (frame.endpoint_address == "0x81" and 
                frame.urb_type == "S" and
                frame.data_length == 0):
                # Check timing - should be very close to previous frame
                if len(transaction_frames) >= 3:
                    time_gap = self.get_time_gap(transaction_frames[-1], frame)
                    if time_gap < 0.002:  # Less than 2ms
                        transaction_frames.append(frame)
        
        return transaction_frames
    
    def collect_bulk_setup(self, frames: List[Frame], start_idx: int) -> List[Frame]:
        """Collect frames for bulk endpoint setup (non-KM003C command)"""
        if start_idx >= len(frames):
            return []
        
        start_frame = frames[start_idx]
        if not (self.is_bulk_transfer(start_frame) and start_frame.urb_type == "S"):
            return []
        
        # Only include this frame - don't try to collect a complete sequence
        # since this is just a buffer setup, not a command-response
        return [start_frame]
    
    def split_transactions(self, frames: List[Frame]) -> List[Transaction]:
        """Split frames into logical transactions"""
        transactions = []
        i = 0
        
        while i < len(frames):
            frame = frames[i]
            
            # Debug removed for final run
            
            # Control transfer
            if self.is_control_transfer(frame) and frame.urb_type == "S":
                transaction_frames = self.collect_control_transfer(frames, i)
                if transaction_frames:
                    tx_id = f"Control_{len([t for t in transactions if t.transaction_type.startswith('Control')]) + 1}"
                    tx = Transaction(
                        transaction_id=tx_id,
                        transaction_type="Control",
                        frames=transaction_frames,
                        start_time=transaction_frames[0].timestamp,
                        duration=transaction_frames[-1].timestamp - transaction_frames[0].timestamp,
                        description=f"Control transfer with {len(transaction_frames)} frames"
                    )
                    transactions.append(tx)
                    i += len(transaction_frames)
                    continue
            
            # KM003C command - check this BEFORE general bulk transfers
            elif self.is_km003c_command(frame):
                transaction_frames = self.collect_km003c_transaction(frames, i)
                if transaction_frames:
                    # Extract command ID for naming
                    cmd_id = self.extract_command_id(frame.payload_hex)
                    if cmd_id:
                        tx_id = f"KM003C_CMD_{cmd_id}"
                        description = f"KM003C command 0x{cmd_id} with {len(transaction_frames)} frames"
                    else:
                        cmd_hex = frame.payload_hex[:8] if len(frame.payload_hex) >= 8 else frame.payload_hex
                        tx_id = f"KM003C_CMD_{cmd_hex}"
                        description = f"KM003C command {cmd_hex} with {len(transaction_frames)} frames"
                    
                    tx = Transaction(
                        transaction_id=tx_id,
                        transaction_type="KM003C_Command",
                        frames=transaction_frames,
                        start_time=transaction_frames[0].timestamp,
                        duration=transaction_frames[-1].timestamp - transaction_frames[0].timestamp,
                        description=description
                    )
                    transactions.append(tx)
                    i += len(transaction_frames)
                    continue
            
            # Bulk setup/other (only if not a KM003C command)
            elif self.is_bulk_transfer(frame) and frame.urb_type == "S":
                transaction_frames = self.collect_bulk_setup(frames, i)
                if transaction_frames:
                    tx_id = f"Bulk_{len([t for t in transactions if t.transaction_type.startswith('Bulk')]) + 1}"
                    tx = Transaction(
                        transaction_id=tx_id,
                        transaction_type="Bulk_Setup",
                        frames=transaction_frames,
                        start_time=transaction_frames[0].timestamp,
                        duration=transaction_frames[-1].timestamp - transaction_frames[0].timestamp if len(transaction_frames) > 1 else 0,
                        description=f"Bulk transfer setup with {len(transaction_frames)} frames"
                    )
                    transactions.append(tx)
                    i += len(transaction_frames)
                    continue
            
            # Skip unmatched frames
            i += 1
        
        return transactions
    
    def output_split_transactions(self, transactions: List[Transaction], output_file: str):
        """Output transactions to JSONL file"""
        with open(output_file, 'w') as f:
            f.write("# Automated transaction splitting for KM003C protocol\n")
            f.write("# Generated by split_transactions.py\n")
            f.write("# Pattern: Control transfers and KM003C command-response sequences\n\n")
            
            for tx_num, tx in enumerate(transactions, 1):
                f.write(f"# Transaction {tx_num}: {tx.description}\n")
                f.write(f"# Start: {tx.start_time:.6f}s, Duration: {tx.duration:.6f}s\n")
                
                for frame in tx.frames:
                    frame_data = frame.raw_data.copy()
                    frame_data['transaction'] = tx_num  # Simple incrementing number
                    frame_data['transaction_type'] = tx.transaction_type
                    frame_data['transaction_name'] = tx.transaction_id  # Descriptive name in separate field
                    f.write(json.dumps(frame_data) + "\n")
                
                f.write("\n")  # Empty line between transactions
    
    def print_summary(self, transactions: List[Transaction]):
        """Print summary of detected transactions"""
        print(f"\nDetected {len(transactions)} transactions:")
        
        type_counts = {}
        for tx in transactions:
            tx_type = tx.transaction_type
            type_counts[tx_type] = type_counts.get(tx_type, 0) + 1
        
        for tx_type, count in type_counts.items():
            print(f"  {tx_type}: {count}")
        
        print(f"\nFirst 10 transactions:")
        for i, tx in enumerate(transactions[:10]):
            frame_count = len(tx.frames)
            print(f"  {i+1:2d}. {tx.transaction_id:15s} {frame_count:2d} frames  {tx.start_time:8.3f}s  {tx.description}")
        
        if len(transactions) > 10:
            print(f"  ... and {len(transactions) - 10} more")


def main():
    if len(sys.argv) != 3:
        print("Usage: python split_transactions.py <input.jsonl> <output.jsonl>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    print(f"Loading frames from {input_file}...")
    splitter = KM003CTransactionSplitter()
    frames = splitter.load_frames(input_file)
    print(f"Loaded {len(frames)} frames")
    
    print("Splitting into transactions...")
    transactions = splitter.split_transactions(frames)
    
    splitter.print_summary(transactions)
    
    print(f"\nWriting transactions to {output_file}...")
    splitter.output_split_transactions(transactions, output_file)
    
    print("Done!")


if __name__ == "__main__":
    main()