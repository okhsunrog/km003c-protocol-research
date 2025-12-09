#!/usr/bin/env python3
"""
Глубокая валидация корреляции битовых масок request → response.

Использует низкоуровневый parse_raw_packet для извлечения ВСЕХ logical packets
из PutData, включая те, что Rust библиотека пока не парсит семантически.

Run: uv run python scripts/validate_bitmask_correlation.py
"""

from __future__ import annotations

import polars as pl
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
import json

try:
    from km003c_lib import parse_raw_packet
    KM003C_LIB_AVAILABLE = True
except ImportError:
    print("❌ km003c_lib not available")
    exit(1)

from km003c_analysis.core import split_usb_transactions


def extract_all_logical_packets_from_raw(payload_hex: str) -> List[Dict[str, Any]]:
    """
    Извлекает ВСЕ logical packets из PutData пакета,
    парся их вручную из raw bytes если нужно.
    """
    try:
        payload_bytes = bytes.fromhex(payload_hex)
        raw_packet = parse_raw_packet(payload_bytes)

        # Новый dict-based API: Data/ SimpleData/ Ctrl варианты
        # Для PutData (с расширенными заголовками) ожидаем вариант "Data"
        if not (isinstance(raw_packet, dict) and "Data" in raw_packet):
            return []

        data_pkt = raw_packet["Data"]
        lps = data_pkt.get("logical_packets", [])

        # Преобразуем к унифицированной структуре с payload_hex для совместимости
        logical_packets = []
        for lp in lps:
            payload = lp.get("payload", b"")
            logical_packets.append(
                {
                    "attribute": lp.get("attribute"),
                    "next": lp.get("next"),
                    "chunk": lp.get("chunk"),
                    "size": lp.get("size"),
                    "payload_hex": payload.hex() if isinstance(payload, (bytes, bytearray)) else "",
                }
            )

        return logical_packets
        
    except Exception as e:
        print(f"⚠️  Error extracting logical packets: {e}")
        return []


def validate_bitmask_correlation():
    """
    Валидация: битовые маски в request ВСЕГДА соответствуют атрибутам в response.
    """
    
    dataset_path = Path("data/processed/usb_master_dataset.parquet")
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        return
    
    print("=" * 80)
    print("ГЛУБОКАЯ ВАЛИДАЦИЯ БИТОВОЙ КОРРЕЛЯЦИИ request → response")
    print("=" * 80)
    print()
    
    df = pl.read_parquet(dataset_path)
    
    # Filter for bulk transfers
    bulk_df = df.filter(
        (pl.col("transfer_type") == "0x03") &
        (pl.col("endpoint_address").is_in(["0x01", "0x81"]))
    )
    
    transactions = split_usb_transactions(bulk_df)
    
    # Track correlations
    correlation_data = {
        "total_pairs": 0,
        "perfect_matches": 0,
        "mismatches": [],
        "by_mask": defaultdict(lambda: {
            "total": 0,
            "expected_attributes": set(),
            "observed_attributes": defaultdict(int),
            "mismatch_cases": []
        }),
    }
    
    # Map bit position to attribute
    BIT_TO_ATTRIBUTE = {
        0: 1,      # bit 0 → attribute 1 (ADC)
        1: 2,      # bit 1 → attribute 2 (AdcQueue)
        3: 8,      # bit 3 → attribute 8 (Settings)
        4: 16,     # bit 4 → attribute 16 (PdPacket)
        9: 512,    # bit 9 → attribute 512 (Unknown512)
    }
    
    # Pending requests by transaction_id
    pending_requests = {}
    
    print("🔍 Анализируем транзакции...")
    
    for row in transactions.iter_rows(named=True):
        if row["payload_hex"] is None or len(row["payload_hex"]) < 8:
            continue
        
        try:
            payload_bytes = bytes.fromhex(row["payload_hex"])
            raw_packet = parse_raw_packet(payload_bytes)
            
            is_request = row["endpoint_address"] == "0x01"
            is_response = row["endpoint_address"] == "0x81"
            
            if is_request and isinstance(raw_packet, dict) and "Ctrl" in raw_packet:
                ctrl = raw_packet["Ctrl"]
                header = ctrl.get("header", {})
                # 0x0C - GetData
                if header.get("packet_type") == 0x0C:
                    mask = header.get("attribute")
                    if mask is not None:
                        # Calculate expected attributes from mask
                        expected_attrs = set()
                        for bit_pos, attr_id in BIT_TO_ATTRIBUTE.items():
                            if mask & (1 << bit_pos):
                                expected_attrs.add(attr_id)

                        pending_requests[header.get("id")] = {
                            "mask": mask,
                            "mask_hex": f"0x{mask:04X}",
                            "expected_attributes": expected_attrs,
                            "timestamp": row["timestamp"],
                        }
            
            elif is_response and isinstance(raw_packet, dict) and "Data" in raw_packet:
                # Extract ALL logical packets
                logical_packets = extract_all_logical_packets_from_raw(row["payload_hex"])

                data_hdr = raw_packet["Data"]["header"]
                resp_id = data_hdr.get("id")

                if resp_id in pending_requests:
                    req = pending_requests.pop(resp_id)
                    
                    # Get observed attributes from logical packets
                    observed_attrs = set(lp["attribute"] for lp in logical_packets)
                    
                    correlation_data["total_pairs"] += 1
                    
                    mask = req["mask"]
                    mask_hex = req["mask_hex"]
                    expected = req["expected_attributes"]
                    
                    # Update statistics
                    correlation_data["by_mask"][mask_hex]["total"] += 1
                    correlation_data["by_mask"][mask_hex]["expected_attributes"] = expected
                    
                    observed_key = str(sorted(observed_attrs))
                    correlation_data["by_mask"][mask_hex]["observed_attributes"][observed_key] += 1
                    
                    # Check if perfect match
                    if observed_attrs == expected:
                        correlation_data["perfect_matches"] += 1
                    else:
                        # Mismatch!
                        mismatch = {
                            "mask": mask_hex,
                            "expected": sorted(expected),
                            "observed": sorted(observed_attrs),
                            "logical_packets": logical_packets,
                        }
                        correlation_data["mismatches"].append(mismatch)
                        correlation_data["by_mask"][mask_hex]["mismatch_cases"].append(mismatch)
        
        except Exception as e:
            # Skip parse errors
            pass
    
    # Report results
    print()
    print("=" * 80)
    print("📊 РЕЗУЛЬТАТЫ ВАЛИДАЦИИ")
    print("=" * 80)
    print()
    
    total = correlation_data["total_pairs"]
    perfect = correlation_data["perfect_matches"]
    mismatches = len(correlation_data["mismatches"])
    
    print(f"Всего request-response пар: {total:,}")
    print(f"Идеальных совпадений: {perfect:,} ({perfect/total*100:.2f}%)")
    print(f"Несовпадений: {mismatches} ({mismatches/total*100:.2f}%)")
    print()
    
    if perfect == total:
        print("✅ ✅ ✅ ИДЕАЛЬНАЯ КОРРЕЛЯЦИЯ!")
        print("   Битовые маски на 100% соответствуют атрибутам в ответах!")
    else:
        print("⚠️  ОБНАРУЖЕНЫ НЕСОВПАДЕНИЯ")
    
    print()
    print("=" * 80)
    print("📋 ДЕТАЛЬНАЯ СТАТИСТИКА ПО МАСКАМ")
    print("=" * 80)
    print()
    
    for mask_hex in sorted(correlation_data["by_mask"].keys(), key=lambda x: int(x, 16)):
        mask_data = correlation_data["by_mask"][mask_hex]
        
        print(f"Маска {mask_hex}:")
        print(f"  Всего запросов: {mask_data['total']}")
        
        expected = mask_data['expected_attributes']
        if expected:
            print(f"  Ожидаемые атрибуты: {sorted(expected)}")
        else:
            print(f"  Ожидаемые атрибуты: [] (пустая маска)")
        
        print(f"  Наблюденные варианты:")
        for observed_str, count in sorted(mask_data['observed_attributes'].items(), 
                                         key=lambda x: x[1], reverse=True):
            pct = count / mask_data['total'] * 100
            observed_set = set(eval(observed_str)) if observed_str != '[]' else set()
            match_marker = "✓" if observed_set == expected else "✗"
            print(f"    {match_marker} {observed_str}: {count} раз ({pct:.1f}%)")
        
        if mask_data['mismatch_cases']:
            print(f"  ⚠️  Несовпадений: {len(mask_data['mismatch_cases'])}")
            for i, mismatch in enumerate(mask_data['mismatch_cases'][:3], 1):  # Show first 3
                print(f"     {i}. Ожидалось {mismatch['expected']}, получено {mismatch['observed']}")
        
        print()
    
    # Detailed mismatch analysis
    if correlation_data["mismatches"]:
        print("=" * 80)
        print("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ НЕСОВПАДЕНИЙ")
        print("=" * 80)
        print()
        
        for i, mismatch in enumerate(correlation_data["mismatches"], 1):
            print(f"Несовпадение #{i}:")
            print(f"  Маска запроса: {mismatch['mask']}")
            print(f"  Ожидаемые атрибуты: {mismatch['expected']}")
            print(f"  Полученные атрибуты: {mismatch['observed']}")
            print(f"  Logical packets в ответе:")
            for lp in mismatch['logical_packets']:
                print(f"    • attribute={lp['attribute']}, next={lp['next']}, size={lp['size']}, payload={lp['payload_hex'][:40]}...")
            print()
    
    # Export detailed results
    output_path = Path("data/processed/bitmask_correlation_validation.json")
    print(f"💾 Экспорт результатов в: {output_path}")
    
    # Convert defaultdicts and sets for JSON
    export_data = {
        "summary": {
            "total_pairs": correlation_data["total_pairs"],
            "perfect_matches": correlation_data["perfect_matches"],
            "mismatches_count": len(correlation_data["mismatches"]),
            "correlation_percentage": perfect / total * 100 if total > 0 else 0,
        },
        "mismatches": correlation_data["mismatches"],
        "by_mask": {
            mask: {
                "total": data["total"],
                "expected_attributes": sorted(data["expected_attributes"]),
                "observed_attributes": dict(data["observed_attributes"]),
                "mismatch_count": len(data["mismatch_cases"]),
            }
            for mask, data in correlation_data["by_mask"].items()
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print("   ✅ Экспортировано!")
    print()
    
    print("=" * 80)
    if perfect == total:
        print("✅ ВАЛИДАЦИЯ ПРОЙДЕНА: 100% КОРРЕЛЯЦИЯ")
    else:
        print(f"⚠️  ВАЛИДАЦИЯ: {perfect/total*100:.2f}% корреляция")
    print("=" * 80)
    print()


if __name__ == "__main__":
    validate_bitmask_correlation()
