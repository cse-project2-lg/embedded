"""Find a full /csi/raw JSONL row by packetId.

Usage:
    python3 rpi_collector/find_csi_raw_packet.py CSI-20260606-...-00000042

The synced.frame message contains raw.csiRawRefs[].packetId and rawLogFile.
This helper scans CSI_RAW_LOG_DIR/csi_raw_YYYYMMDD.jsonl files and prints the
full csi.raw record, including payloadBase64.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from config import CSI_RAW_LOG_DIR


def candidate_files(raw_log_file: Optional[str]) -> Iterable[Path]:
    base_dir = Path(CSI_RAW_LOG_DIR).expanduser()
    if raw_log_file:
        yield base_dir / raw_log_file
        return
    yield from sorted(base_dir.glob("csi_raw_*.jsonl"))


def find_packet(packet_id: str, raw_log_file: Optional[str] = None) -> Optional[Dict[str, Any]]:
    for path in candidate_files(raw_log_file):
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("packetId") == packet_id:
                    return row
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find full CSI raw packet by packetId")
    parser.add_argument("packet_id", help="packetId from raw.csiRawRefs[]")
    parser.add_argument("--file", dest="raw_log_file", help="Optional csi_raw_YYYYMMDD.jsonl file name")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    packet = find_packet(args.packet_id, args.raw_log_file)
    if packet is None:
        raise SystemExit(f"packetId not found: {args.packet_id}")
    print(json.dumps(packet, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
