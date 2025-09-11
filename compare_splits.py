import json
from itertools import groupby

def parse_transaction_file(filepath):
    """Parses a transaction file, grouping frames by transaction ID."""
    transactions = []
    try:
        with open(filepath, 'r') as f:
            lines = [line for line in f if line.strip() and not line.strip().startswith('#')]
            frames = [json.loads(line) for line in lines]
            
            # Group frames by the 'transaction_id'
            for key, group in groupby(frames, key=lambda x: x.get('transaction_id')):
                if key is not None:
                    transactions.append(list(group))

    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON in {filepath}: {e}")
        return None
        
    return transactions

def compare_transactions(t1, t2):
    """Compares two individual transactions."""
    if len(t1) != len(t2):
        return False
    # Compare essential fields of each frame
    for f1, f2 in zip(t1, t2):
        if f1.get('frame_number') != f2.get('frame_number') or \
           f1.get('urb_id') != f2.get('urb_id') or \
           f1.get('payload_hex') != f2.get('payload_hex'):
            return False
    return True

def main():
    gemini_file = 'for_manual_split_gemini_transactions.jsonl'
    claude_file = 'for_manual_split_claude_manually_split.jsonl'
    
    gemini_transactions = parse_transaction_file(gemini_file)
    claude_transactions = parse_transaction_file(claude_file)
    
    if gemini_transactions is None or claude_transactions is None:
        return

    print("--- Comparison Report ---")
    print(f"Gemini File: {len(gemini_transactions)} transactions")
    print(f"Claude File: {len(claude_transactions)} transactions")
    
    if len(gemini_transactions) != len(claude_transactions):
        print("\nResult: Files have a different number of transactions.")
    else:
        print("\nFiles have the same number of transactions. Checking for content differences...")
        
        differences_found = False
        for i, (gemini_t, claude_t) in enumerate(zip(gemini_transactions, claude_transactions)):
            if not compare_transactions(gemini_t, claude_t):
                differences_found = True
                print(f"\nDifference found in Transaction #{i+1}")
                print(f"  Gemini (Frames: {len(gemini_t)}): {[f['frame_number'] for f in gemini_t]}")
                print(f"  Claude (Frames: {len(claude_t)}): {[f['frame_number'] for f in claude_t]}")

        if not differences_found:
            print("\nResult: No differences found. The transaction groupings are identical.")
        else:
            print("\nResult: Differences were found in the transaction groupings.")

if __name__ == "__main__":
    main()
