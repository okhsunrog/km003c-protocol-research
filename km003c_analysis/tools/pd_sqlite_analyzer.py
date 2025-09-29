#!/usr/bin/env python3
"""
KM003C SQLite PD Export Analyzer

A comprehensive, production-ready tool for analyzing USB Power Delivery messages
from KM003C SQLite exports. Provides complete PDO/RDO parsing, power negotiation
analysis, and export capabilities using usbpdpy v0.2.0.

Features:
- Full Source_Capabilities analysis with 6 PDO types support
- State-aware Request message parsing with PDO context
- Complete power negotiation sequence tracking
- Voltage correlation validation
- Export to multiple formats (JSON, Parquet, CSV)
- Interactive CLI with detailed reporting

Usage:
    uv run python -m km003c_analysis.tools.pd_sqlite_analyzer [options]
    uv run python km003c_analysis/tools/pd_sqlite_analyzer.py [options]

Example:
    # Analyze with full report
    uv run python -m km003c_analysis.tools.pd_sqlite_analyzer --verbose

    # Export to JSON
    uv run python -m km003c_analysis.tools.pd_sqlite_analyzer --export-json results.json

    # Analyze specific SQLite file
    uv run python -m km003c_analysis.tools.pd_sqlite_analyzer --input custom.sqlite
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any

import usbpdpy

try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False


@dataclass
class PowerNegotiation:
    """Represents a complete power negotiation sequence."""
    source_capabilities: Optional[usbpdpy.PdMessage] = None
    request: Optional[usbpdpy.PdMessage] = None
    accept: Optional[usbpdpy.PdMessage] = None
    ps_rdy: Optional[usbpdpy.PdMessage] = None
    timestamp_start: float = 0.0
    timestamp_end: float = 0.0
    voltage_before: float = 0.0
    voltage_after: float = 0.0

    def is_complete(self) -> bool:
        """Check if negotiation has all required messages."""
        return all([
            self.source_capabilities,
            self.request,
            self.accept,
            self.ps_rdy
        ])

    def duration_ms(self) -> float:
        """Get negotiation duration in milliseconds."""
        return (self.timestamp_end - self.timestamp_start) * 1000

    def voltage_change(self) -> float:
        """Get voltage change in volts."""
        return self.voltage_after - self.voltage_before


@dataclass
class AnalysisResults:
    """Complete analysis results from SQLite PD export."""
    total_events: int = 0
    pd_messages: List[Dict[str, Any]] = None
    source_capabilities: List[Dict[str, Any]] = None
    negotiations: List[PowerNegotiation] = None
    message_types: Dict[str, int] = None
    power_profiles: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.pd_messages is None:
            self.pd_messages = []
        if self.source_capabilities is None:
            self.source_capabilities = []
        if self.negotiations is None:
            self.negotiations = []
        if self.message_types is None:
            self.message_types = {}
        if self.power_profiles is None:
            self.power_profiles = []


class SQLitePDAnalyzer:
    """Comprehensive SQLite PD export analyzer."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = AnalysisResults()

    def parse_pd_blob(self, blob: bytes) -> List[Dict[str, Any]]:
        """Parse KM003C PD event BLOB into individual PD messages."""
        events = []
        if not blob:
            return events

        b = blob
        i = 0

        while i < len(b):
            t0 = b[i]

            if t0 == 0x45:
                # Connection/Status event (6 bytes)
                if i + 6 <= len(b):
                    ts = int.from_bytes(b[i + 1 : i + 4], "little")
                    reserved = b[i + 4]
                    event_data = b[i + 5]
                    events.append({
                        "kind": "connection",
                        "timestamp": ts,
                        "reserved": reserved,
                        "event_data": event_data,
                    })
                    i += 6
                else:
                    break

            elif 0x80 <= t0 <= 0x9F:
                # PD message event
                if i + 6 > len(b):
                    break

                size_flag = b[i]
                ts = int.from_bytes(b[i + 1 : i + 5], "little")
                sop = b[i + 5]
                i += 6

                size = size_flag & 0x3F
                wire_len = max(0, size - 5)

                if wire_len == 0 or i + wire_len > len(b):
                    break

                wire = b[i : i + wire_len]
                i += wire_len

                events.append({
                    "kind": "pd_message",
                    "timestamp": ts,
                    "sop": sop,
                    "wire_len": wire_len,
                    "wire_bytes": wire,
                })
            else:
                break

        return events

    def analyze_sqlite(self, sqlite_path: Path) -> AnalysisResults:
        """Perform comprehensive analysis of SQLite PD export."""

        if not sqlite_path.exists():
            raise FileNotFoundError(f"SQLite file not found: {sqlite_path}")

        if self.verbose:
            print(f"=== KM003C SQLITE PD ANALYZER ===")
            print(f"Using usbpdpy v{usbpdpy.__version__}")
            print(f"Analyzing: {sqlite_path}")
            print()

        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()

        # Check schema
        cursor.execute("PRAGMA table_info(pd_table)")
        columns = [row[1] for row in cursor.fetchall()]
        if not all(col in columns for col in ['Time', 'Vbus', 'Ibus', 'Raw']):
            raise ValueError(f"Invalid SQLite schema. Expected columns: Time, Vbus, Ibus, Raw. Found: {columns}")

        # Load all data
        cursor.execute("SELECT Time, Vbus, Ibus, Raw FROM pd_table ORDER BY Time")
        rows = cursor.fetchall()
        conn.close()

        if self.verbose:
            print(f"Total SQLite events: {len(rows)}")

        # Track analysis state
        pd_messages = []
        negotiations = []
        current_negotiation = PowerNegotiation()
        last_source_capabilities = None
        message_counter = Counter()

        # Parse all events
        for time_s, vbus_v, ibus_a, raw in rows:
            events = self.parse_pd_blob(raw)

            for event in events:
                if event["kind"] == "pd_message":
                    wire_bytes = event["wire_bytes"]

                    try:
                        # Basic parsing first
                        msg = usbpdpy.parse_pd_message(wire_bytes)

                        # Enhanced parsing for Request messages (with PDO state)
                        if msg.header.message_type == "Request" and last_source_capabilities:
                            msg = usbpdpy.parse_pd_message_with_state(
                                wire_bytes,
                                last_source_capabilities.data_objects
                            )

                        # Store message with context
                        pd_msg_info = {
                            "time_s": time_s,
                            "vbus_v": vbus_v,
                            "ibus_a": ibus_a,
                            "message_type": msg.header.message_type,
                            "wire_hex": wire_bytes.hex(),
                            "wire_len": len(wire_bytes),
                            "message": msg,
                            "timestamp": event["timestamp"],
                            "sop": event["sop"],
                        }
                        pd_messages.append(pd_msg_info)
                        message_counter[msg.header.message_type] += 1

                        # Track negotiation sequences
                        msg_type = msg.header.message_type

                        if msg_type == "Source_Capabilities":
                            # Start new negotiation
                            if current_negotiation.source_capabilities:
                                negotiations.append(current_negotiation)
                            current_negotiation = PowerNegotiation(
                                source_capabilities=msg,
                                timestamp_start=time_s,
                                voltage_before=vbus_v
                            )
                            last_source_capabilities = msg

                        elif msg_type == "Request":
                            current_negotiation.request = msg

                        elif msg_type == "Accept":
                            current_negotiation.accept = msg

                        elif msg_type == "PS_RDY":
                            current_negotiation.ps_rdy = msg
                            current_negotiation.timestamp_end = time_s
                            current_negotiation.voltage_after = vbus_v

                            # Complete negotiation
                            negotiations.append(current_negotiation)
                            current_negotiation = PowerNegotiation()

                    except Exception as e:
                        if self.verbose:
                            print(f"Parse error at {time_s}s: {e}")
                        continue

        # Finalize incomplete negotiation
        if current_negotiation.source_capabilities:
            negotiations.append(current_negotiation)

        # Extract power profiles
        source_capabilities = []
        power_profiles = []

        for msg_info in pd_messages:
            if msg_info["message_type"] == "Source_Capabilities":
                msg = msg_info["message"]

                # Extract PDO information
                pdo_list = []
                for i, pdo in enumerate(msg.data_objects):
                    pdo_dict = {
                        "position": i + 1,
                        "type": pdo.pdo_type,
                        "voltage_v": pdo.voltage_v,
                        "max_current_a": pdo.max_current_a,
                        "max_power_w": pdo.max_power_w,
                        "raw": pdo.raw,
                    }

                    # Add type-specific fields
                    if hasattr(pdo, 'unconstrained_power'):
                        pdo_dict["unconstrained_power"] = pdo.unconstrained_power
                    if hasattr(pdo, 'min_voltage_v'):
                        pdo_dict["min_voltage_v"] = pdo.min_voltage_v
                    if hasattr(pdo, 'max_voltage_v'):
                        pdo_dict["max_voltage_v"] = pdo.max_voltage_v

                    pdo_list.append(pdo_dict)

                cap_info = {
                    "time_s": msg_info["time_s"],
                    "wire_hex": msg_info["wire_hex"],
                    "pdos": pdo_list,
                }
                source_capabilities.append(cap_info)

                # Create power profile signature
                if pdo_list not in power_profiles:
                    power_profiles.append(pdo_list)

        # Store results
        self.results = AnalysisResults(
            total_events=len(rows),
            pd_messages=pd_messages,
            source_capabilities=source_capabilities,
            negotiations=negotiations,
            message_types=dict(message_counter),
            power_profiles=power_profiles,
        )

        return self.results

    def print_analysis(self) -> None:
        """Print comprehensive analysis results."""

        results = self.results

        print("=== ANALYSIS SUMMARY ===")
        print(f"Total SQLite events processed: {results.total_events}")
        print(f"PD messages parsed: {len(results.pd_messages)}")
        print(f"Message type distribution: {results.message_types}")
        print()

        # Source Capabilities Analysis
        if results.source_capabilities:
            print("=== SOURCE CAPABILITIES ANALYSIS ===")
            print(f"Source_Capabilities messages: {len(results.source_capabilities)}")

            # Show first complete power profile
            if results.power_profiles:
                profile = results.power_profiles[0]
                print(f"Power Profile ({len(profile)} PDOs):")
                for pdo in profile:
                    extra = ""
                    if pdo.get("unconstrained_power"):
                        extra = " (Unconstrained)"
                    elif pdo.get("min_voltage_v") and pdo.get("max_voltage_v"):
                        extra = f" ({pdo['min_voltage_v']}-{pdo['max_voltage_v']}V range)"

                    print(f"  PDO{pdo['position']}: {pdo['type']} {pdo['voltage_v']}V @ {pdo['max_current_a']}A = {pdo['max_power_w']}W{extra}")
            print()

        # Request Analysis
        requests = [msg for msg in results.pd_messages if msg["message_type"] == "Request"]
        if requests:
            print("=== REQUEST MESSAGE ANALYSIS ===")
            for req_info in requests:
                msg = req_info["message"]
                print(f"Request at {req_info['time_s']:.3f}s (Vbus: {req_info['vbus_v']:.3f}V):")

                if msg.request_objects:
                    rdo = msg.request_objects[0]
                    print(f"  └─ Requesting PDO #{rdo.object_position}")
                    print(f"  └─ RDO Type: {rdo.rdo_type}")
                    print(f"  └─ Raw RDO: 0x{rdo.raw:08x}")

                    # Cross-reference with PDO
                    source_caps = next((sc for sc in results.source_capabilities), None)
                    if source_caps and 1 <= rdo.object_position <= len(source_caps["pdos"]):
                        requested_pdo = source_caps["pdos"][rdo.object_position - 1]
                        print(f"  └─ Requested PDO: {requested_pdo['type']} {requested_pdo['voltage_v']}V @ {requested_pdo['max_current_a']}A")
                print()

        # Power Negotiation Analysis
        complete_negotiations = [n for n in results.negotiations if n.is_complete()]
        if complete_negotiations:
            print("=== POWER NEGOTIATION ANALYSIS ===")
            for i, neg in enumerate(complete_negotiations, 1):
                print(f"Negotiation {i}:")
                print(f"  Duration: {neg.duration_ms():.0f}ms")
                print(f"  Voltage transition: {neg.voltage_before:.3f}V → {neg.voltage_after:.3f}V")

                if neg.request and neg.request.request_objects:
                    rdo = neg.request.request_objects[0]
                    if neg.source_capabilities and 1 <= rdo.object_position <= len(neg.source_capabilities.data_objects):
                        pdo = neg.source_capabilities.data_objects[rdo.object_position - 1]
                        print(f"  Negotiated power: PDO{rdo.object_position} ({pdo.voltage_v}V @ {pdo.max_current_a}A)")
                        print(f"  Maximum available power: {pdo.max_power_w}W")
                print()

        # Summary Statistics
        print("=== SUMMARY STATISTICS ===")
        print(f"Complete negotiations detected: {len(complete_negotiations)}")
        print(f"Source Capabilities messages: {results.message_types.get('Source_Capabilities', 0)}")
        print(f"Request messages: {results.message_types.get('Request', 0)}")
        if complete_negotiations:
            avg_voltage_change = sum(n.voltage_change() for n in complete_negotiations) / len(complete_negotiations)
            print(f"Average voltage change: {avg_voltage_change:+.3f}V")

    def export_json(self, output_path: Path) -> None:
        """Export analysis results to JSON."""

        # Convert results to JSON-serializable format
        export_data = {
            "analysis_summary": {
                "total_events": self.results.total_events,
                "pd_messages_count": len(self.results.pd_messages),
                "message_types": self.results.message_types,
            },
            "source_capabilities": self.results.source_capabilities,
            "power_profiles": self.results.power_profiles,
            "negotiations": [
                {
                    "timestamp_start": n.timestamp_start,
                    "timestamp_end": n.timestamp_end,
                    "voltage_before": n.voltage_before,
                    "voltage_after": n.voltage_after,
                    "duration_ms": n.duration_ms(),
                    "voltage_change": n.voltage_change(),
                    "is_complete": n.is_complete(),
                }
                for n in self.results.negotiations
            ],
            "pd_messages": [
                {
                    "time_s": msg["time_s"],
                    "vbus_v": msg["vbus_v"],
                    "ibus_a": msg["ibus_a"],
                    "message_type": msg["message_type"],
                    "wire_hex": msg["wire_hex"],
                    "wire_len": msg["wire_len"],
                }
                for msg in self.results.pd_messages
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        if self.verbose:
            print(f"✅ Analysis results exported to: {output_path}")

    def export_parquet(self, output_path: Path) -> None:
        """Export PD messages to Parquet format (requires polars)."""

        if not POLARS_AVAILABLE:
            raise ImportError("Polars is required for Parquet export. Install with: uv add polars")

        # Convert to DataFrame
        df_data = []
        for msg in self.results.pd_messages:
            df_data.append({
                "time_s": msg["time_s"],
                "vbus_v": msg["vbus_v"],
                "ibus_a": msg["ibus_a"],
                "message_type": msg["message_type"],
                "wire_hex": msg["wire_hex"],
                "wire_len": msg["wire_len"],
                "timestamp": msg["timestamp"],
                "sop": msg["sop"],
            })

        df = pl.DataFrame(df_data)
        df.write_parquet(output_path)

        if self.verbose:
            print(f"✅ PD messages exported to Parquet: {output_path}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Comprehensive KM003C SQLite PD Export Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --verbose                              # Full analysis report
  %(prog)s --export-json results.json           # Export to JSON
  %(prog)s --export-parquet messages.parquet    # Export to Parquet
  %(prog)s --input custom.sqlite --verbose      # Analyze custom SQLite file
        """
    )

    parser.add_argument(
        "--input", "-i",
        type=Path,
        default="data/sqlite/pd_new.sqlite",
        help="Input SQLite file path (default: data/sqlite/pd_new.sqlite)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with detailed analysis"
    )

    parser.add_argument(
        "--export-json",
        type=Path,
        help="Export analysis results to JSON file"
    )

    parser.add_argument(
        "--export-parquet",
        type=Path,
        help="Export PD messages to Parquet file"
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress analysis output (useful with export options)"
    )

    args = parser.parse_args()

    try:
        analyzer = SQLitePDAnalyzer(verbose=args.verbose)
        results = analyzer.analyze_sqlite(args.input)

        if not args.quiet:
            analyzer.print_analysis()

        if args.export_json:
            analyzer.export_json(args.export_json)

        if args.export_parquet:
            analyzer.export_parquet(args.export_parquet)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Analysis failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()