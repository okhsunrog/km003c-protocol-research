# USB Transaction Splitting Guide for KM003C Protocol Analysis

## Overview
This document provides comprehensive guidance for splitting USB capture frames into logical transactions for the KM003C USB-C power analyzer protocol. The captures are from Linux's `usbmon` interface via Wireshark, showing USB Request Block (URB) level data.

## Critical Background: Understanding URBs

### What is a URB?
A URB (USB Request Block) is a kernel data structure used to manage USB I/O operations. In our captures:
- **Submit (S)**: When the host initiates a USB operation
- **Complete (C)**: When the operation finishes (success, error, or data received)
- **urb_id**: The memory address of the URB structure (NOT a unique transaction ID!)

### ⚠️ Critical Warning: URB ID Reuse
The `urb_id` field is a **memory address that gets reused**. The same address can appear in many unrelated transactions throughout a capture. **Never group frames by urb_id alone** - this is the most common analysis mistake.

## USB Transfer Types in KM003C

The KM003C uses two transfer types that require different grouping logic:

### 1. Control Transfers (transfer_type = "0x02")
Used for device enumeration and configuration. These follow the standard USB control transfer pattern:
- **Setup Stage**: Submit with setup packet data
- **Data Stage** (optional): Data transfer if wLength > 0  
- **Status Stage**: Complete acknowledging the transfer

**Grouping Rule**: Group all frames with the same urb_id that form a complete control transfer sequence.

### 2. Bulk Transfers (transfer_type = "0x03") 
Used for actual data communication (commands and responses). The KM003C uses a sophisticated pipelined pattern for performance optimization.

## The KM003C Bulk Transfer Pattern

### Standard Command-Response Pattern
The KM003C implements a performance-optimized pattern for ADC data requests:

```
Transaction N:
1. Command Submit    (endpoint 0x01, e.g., "0c190200" = CmdGetSimpleAdcData)
2. Command Complete  (endpoint 0x01, empty ACK)
3. Data Complete     (endpoint 0x81, ADC data response)
4. Pre-position Submit (endpoint 0x81, empty, preparing for NEXT transaction)
```

### Key Insight: Pre-positioned Receive Buffers
The last frame of each transaction is a Submit that prepares the receive buffer for the NEXT transaction. This eliminates round-trip latency by having the receive buffer ready before the next command is even sent.

### Example with Timing Analysis
```
Frame 1495: 21.066064 - S (0x01) Command 0x18
Frame 1496: 21.066121 - C (0x01) ACK
Frame 1497: 21.066184 - C (0x81) Data for 0x18
Frame 1498: 21.067844 - S (0x81) Pre-position for next   <-- Part of transaction 0x18!

--- 200ms gap indicates new transaction ---

Frame 1499: 21.275984 - S (0x01) Command 0x19            <-- New transaction starts
Frame 1500: 21.276048 - C (0x01) ACK  
Frame 1501: 21.276111 - C (0x81) Data for 0x19 (uses URB from frame 1498!)
Frame 1502: 21.277809 - S (0x81) Pre-position for next
```

## Transaction Boundary Detection Rules

### Rule 1: Time Gap Analysis
- Gaps > 100ms usually indicate transaction boundaries
- The pre-positioned Submit happens immediately after data (< 2ms)
- New commands come after longer delays (typically 200ms+)

### Rule 2: Endpoint Patterns
- **0x01** = OUT endpoint (host → device commands)
- **0x81** = IN endpoint (device → host responses)
- Commands always start on 0x01
- Responses always come on 0x81

### Rule 3: URB ID Correlation
For bulk transfers, the pre-positioned Submit creates a URB that will be used by the NEXT transaction:
1. Pre-positioned S creates URB with id X
2. Next transaction's data C uses the same URB id X
3. This creates an "interleaved" pattern where URB IDs span transaction boundaries

## Step-by-Step Splitting Algorithm

### For Control Transfers:
1. Find Submit with transfer_type = "0x02"
2. Collect all subsequent frames with same urb_id
3. Stop when you see the final Complete
4. This entire sequence = one transaction

### For Bulk Transfers:
1. Find Submit on endpoint 0x01 with payload (command)
2. Include the next Complete on 0x01 (ACK)
3. Include the next Complete on 0x81 (response data)
4. Include the immediately following Submit on 0x81 (pre-position)
5. This 4-frame sequence = one transaction

### Special Cases:

#### Case 1: Session Start
The first transaction might not have a pre-positioned Submit because there was no previous transaction to provide it.

#### Case 2: Interrupted Sequences  
If urb_status = "-2" (ENOENT), the transaction was cancelled. Group these separately.

#### Case 3: Multiple Submits
Sometimes you'll see multiple Submits before any Completes. These are queued operations. Match each Submit with its corresponding Complete by urb_id.

## Data Fields Required for Analysis

Essential fields needed in your data structure:
```json
{
  "frame": 1499,                    // Frame number
  "time": 21.275984,                // Timestamp (seconds)
  "transfer_type": "0x03",          // Critical: 0x02=Control, 0x03=Bulk
  "endpoint": "0x01",               // Endpoint address
  "urb": "S",                       // URB type: S=Submit, C=Complete
  "urb_status": "0",                // Status: 0=success, -115=pending, -2=cancelled
  "urb_id": "0xffff894bba8d00c0",  // URB memory address (reused!)
  "src": "host",                    // Source
  "dst": "1.12.1",                  // Destination  
  "len": 4,                         // Payload length
  "payload_hex": "0c190200"         // Actual data
}
```

## Common Pitfalls to Avoid

### ❌ Pitfall 1: Grouping by URB ID
Never group all frames with the same urb_id together. The same memory address is reused for unrelated transactions.

### ❌ Pitfall 2: Starting Transaction at Pre-positioned Submit
The pre-positioned Submit belongs to the PREVIOUS transaction, not the next one. Look for time gaps to identify true transaction starts.

### ❌ Pitfall 3: Ignoring Transfer Type
Control and Bulk transfers have completely different patterns. Always check transfer_type first.

### ❌ Pitfall 4: Missing the Pipeline Pattern
The response data Complete uses the URB from the PREVIOUS transaction's pre-positioned Submit. This interleaving is intentional for performance.

## Validation Checklist

After splitting, verify your transactions:

- [ ] Each ADC command transaction has exactly 4 frames
- [ ] Pre-positioned Submit is immediately after data Complete (< 2ms)
- [ ] Time gap before new command is typically > 100ms
- [ ] Command sequence numbers increment (0x18, 0x19, 0x1a...)
- [ ] Response data matches command ID (command 0x19 gets response with 0x19 byte)

## Example Code Structure

```python
def split_transactions(frames):
    transactions = []
    i = 0
    
    while i < len(frames):
        frame = frames[i]
        
        # Control transfer
        if frame["transfer_type"] == "0x02" and frame["urb"] == "S":
            transaction = collect_control_transfer(frames, i)
            transactions.append(transaction)
            i = len(transaction)
            
        # Bulk transfer command
        elif (frame["transfer_type"] == "0x03" and 
              frame["endpoint"] == "0x01" and 
              frame["urb"] == "S" and 
              frame["len"] > 0):
            # Collect: Command S, Command C, Data C, Pre-position S
            transaction = collect_bulk_command(frames, i)
            transactions.append(transaction)
            i += len(transaction)
            
        else:
            i += 1  # Skip orphaned frames
            
    return transactions
```

## Testing Your Implementation

1. **Count Check**: Verify you have approximately N/4 transactions for N bulk frames
2. **Timing Check**: Plot inter-transaction delays - should show consistent patterns
3. **Sequence Check**: ADC command IDs should increment sequentially
4. **URB Check**: Pre-positioned Submit URB should match next transaction's data Complete

## Final Notes

The KM003C's pipelined architecture is sophisticated but follows consistent patterns. The key insight is that each transaction "borrows" the receive buffer that was prepared by the previous transaction, creating an elegant pipeline that minimizes USB latency.

When in doubt:
1. Look at timing gaps to identify transaction boundaries
2. Remember that pre-positioned Submits belong to the transaction that created them
3. Use endpoint addresses to understand data flow direction
4. Verify command/response ID matching in the payload

This pattern is consistent throughout the KM003C protocol and understanding it is crucial for correct protocol analysis.