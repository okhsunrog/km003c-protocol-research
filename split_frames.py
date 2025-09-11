import json
from collections import deque

def group_control_transaction(frames_deque):
    if not frames_deque:
        return None
    
    # Start with the first frame, which must be a control 'S'
    start_frame = frames_deque[0]
    if not (start_frame.get("transfer_type") == "0x02" and start_frame.get("urb_type") == "S"):
        return None
        
    urb_id = start_frame['urb_id']
    transaction = [frames_deque.popleft()]
    
    # Find the corresponding 'C' frame
    found_c = False
    for i in range(len(frames_deque)):
        if frames_deque[i]['urb_id'] == urb_id and frames_deque[i]['urb_type'] == 'C':
            transaction.append(frames_deque[i])
            # To handle out-of-order frames, we remove the found frame from its current position
            del frames_deque[i]
            found_c = True
            break
            
    if found_c:
        return transaction
    else:
        # If no 'C' is found, return the 'S' frame to the queue
        frames_deque.appendleft(transaction[0])
        return None

def group_bulk_transaction(frames_deque):
    if len(frames_deque) < 4:
        return None
        
    # Pattern: S(0x01), C(0x01), C(0x81), S(0x81)
    s1 = frames_deque[0]
    c1 = frames_deque[1]
    c2 = frames_deque[2]
    s2 = frames_deque[3]
    
    # Check for the specific 4-frame bulk ADC command pattern
    if (s1.get("endpoint_address") == "0x01" and s1.get("urb_type") == "S" and
        c1.get("endpoint_address") == "0x01" and c1.get("urb_type") == "C" and
        c2.get("endpoint_address") == "0x81" and c2.get("urb_type") == "C" and
        s2.get("endpoint_address") == "0x81" and s2.get("urb_type") == "S" and
        s1.get("urb_id") == c1.get("urb_id")):
        
        # Consume the frames from the deque
        transaction = [frames_deque.popleft() for _ in range(4)]
        return transaction
        
    return None

def main():
    # It's safer to work from the backup
    input_file = 'for_manual_split_gemini.jsonl' 
    with open(input_file, 'r') as f:
        # Filter out comments and blank lines
        frames = [json.loads(line) for line in f if line.strip() and not line.strip().startswith('#')]

    # Sort frames by timestamp to ensure chronological order
    frames.sort(key=lambda x: x['timestamp'])
    frames_deque = deque(frames)
    
    transactions = []
    unmatched_frames = []

    while frames_deque:
        # Try to match a control transaction first
        control_trans = group_control_transaction(deque([f for f in frames_deque if f.get("transfer_type") == "0x02"]))
        if control_trans:
            transactions.append(control_trans)
            # Remove matched frames from the main deque
            for frame in control_trans:
                if frame in frames_deque:
                    frames_deque.remove(frame)
            continue

        # If no control, try to match a bulk transaction
        bulk_trans = group_bulk_transaction(frames_deque)
        if bulk_trans:
            transactions.append(bulk_trans)
            continue
            
        # If neither pattern matches, it's an orphaned frame
        unmatched_frames.append(frames_deque.popleft())

    # Sort transactions based on the timestamp of their first frame
    transactions.sort(key=lambda t: t[0]['timestamp'])

    output_file = 'for_manual_split_gemini_transactions.jsonl'
    with open(output_file, 'w') as f:
        for i, transaction in enumerate(transactions):
            f.write(f"# Transaction {i+1}\n")
            for frame in transaction:
                frame['transaction_id'] = i + 1
                f.write(json.dumps(frame) + '\n')
            f.write('\n')
        
        if unmatched_frames:
            f.write("# Unmatched Frames\n")
            for frame in unmatched_frames:
                f.write(json.dumps(frame) + '\n')
            
    print(f"Successfully split into {len(transactions)} transactions.")
    if unmatched_frames:
        print(f"Found {len(unmatched_frames)} unmatched frames.")
    print(f"Corrected file is '{output_file}'")

if __name__ == "__main__":
    main()
