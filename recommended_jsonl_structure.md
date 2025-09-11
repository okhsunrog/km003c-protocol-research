# Recommended JSONL Structure for Transaction Analysis

## Essential Fields (MUST HAVE)
```json
{
  "transaction_id": 1,           // Logical transaction ID
  "frame": 1439,                  // Frame number
  "time": 18.145973,             // Relative timestamp
  "transfer_type": "0x03",       // Critical: 0x02=Control, 0x03=Bulk
  "endpoint": "0x01",            // Endpoint address
  "urb": "S",                    // URB type (S/C)
  "urb_status": "-115",          // URB status code
  "urb_id": "0xffff894bba8d1440",
  "src": "host",
  "dst": "1.12.1",
  "len": 4,                      // Data length
  "payload_hex": "0c0a0200",
  "parsed": {...}                // Optional parsed data
}
```

## Additional Useful Fields
```json
{
  "data_flag": "<",              // Data direction flag
  "setup_flag": "\\0",           // Setup packet flag
  "bmrequest_type": "0x80",     // For control transfers
  "brequest": "6",               // For control transfers
  "descriptor_type": "0x01"      // For descriptor requests
}
```

## Transaction Grouping Rules

### Rule 1: Control Transfer Grouping (transfer_type = 0x02)
Group all frames with same urb_id that form a complete control transfer:
- Setup stage (S with bmrequest_type)
- Data stage (if wlength > 0)
- Status stage (final C)

### Rule 2: Bulk Transfer Command-Response (transfer_type = 0x03)
Group related bulk transfers:
1. Command Submit (S with payload)
2. Command Complete (C, usually empty)
3. Pre-positioned request (S, empty, different urb_id)
4. Response data (C with payload, matches pre-positioned urb_id)

### Rule 3: Bulk Polling (transfer_type = 0x03)
Single S→C pair with empty payloads

### Rule 4: Time-based Boundaries
New transaction if time gap > 100ms (except for long operations)

## Example Grouped Transactions

### Control Transfer Example
```json
// Transaction 1: Get Device Descriptor
{"transaction_id": 1, "frame": 1, "transfer_type": "0x02", "urb": "S", "bmrequest_type": "0x80", "brequest": "6", "wlength": 18, ...}
{"transaction_id": 1, "frame": 2, "transfer_type": "0x02", "urb": "C", "len": 18, "payload_hex": "12010002...", ...}
```

### Bulk Transfer Example  
```json
// Transaction 2: ADC Data Request
{"transaction_id": 2, "frame": 1439, "transfer_type": "0x03", "endpoint": "0x01", "urb": "S", "payload_hex": "0c0a0200", ...}
{"transaction_id": 2, "frame": 1440, "transfer_type": "0x03", "endpoint": "0x01", "urb": "C", "len": 0, ...}
{"transaction_id": 2, "frame": 1441, "transfer_type": "0x03", "endpoint": "0x81", "urb": "C", "payload_hex": "410a8202...", ...}
```