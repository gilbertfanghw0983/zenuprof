import sys
import csv
from datetime import datetime, timedelta

CSV_PATH = "l2_zen4_2.csv"
PHASE_PATH = "phase.csv"
L3_MISS_RATE_OFFSET = 2  # within each CCX block: 0=L3 Access, 1=L3 Miss, 2=L3 Miss %
ZEN_L3_MISS_PATH = "l3missrate.csv"


def parse_cpu_args(args):
    cpu_ids = []
    for arg in args:
        if "-" in arg:
            lo, hi = arg.split("-", 1)
            cpu_ids.extend(range(int(lo), int(hi) + 1))
        else:
            cpu_ids.append(int(arg))
    return cpu_ids


def parse_topology(lines):
    cpu_to_ccx = {}
    in_topology = False
    skip_header = False
    for line in lines:
        stripped = line.strip()
        if stripped == "CPU Topology:":
            in_topology = True
            skip_header = True
            continue
        if in_topology:
            if skip_header:
                skip_header = False
                continue
            if not stripped or not stripped[0].isdigit():
                break
            parts = stripped.split(",", 2)
            ccx = int(parts[1].strip())
            for cpu in parts[2].strip().split():
                cpu_to_ccx[int(cpu)] = ccx
    return cpu_to_ccx


def parse_profile_time(lines):
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Profile Time:"):
            time_str = stripped.split(":", 1)[1].strip()
            # Format: YYYY/MM/DD HH:MM:SS:mmm
            dt, ms = time_str.rsplit(":", 1)
            base = datetime.strptime(dt, "%Y/%m/%d %H:%M:%S")
            return base + timedelta(milliseconds=int(ms))
    raise ValueError("Profile Time not found in CSV")


def parse_phases(phase_path):
    phases = []
    with open(phase_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            start = datetime.fromisoformat(row["median_start_timestamp"].strip())
            end = datetime.fromisoformat(row["end_timestamp"].strip())
            phases.append((row["op"], start, end))
    return phases


def relative_to_absolute(rel_ts, profile_time):
    # Format: HH:MM:SS:mmm
    parts = rel_ts.split(":")
    h, m, s, ms = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    return profile_time + timedelta(hours=h, minutes=m, seconds=s, milliseconds=ms)


def get_phase(abs_ts, phases):
    for op, start, end in phases:
        if start <= abs_ts < end:
            return op
    return "-"


def parse_l3_miss_rates_avg(lines, ccx_ids, profile_time, phases):
    # Find the column index of L3 Miss % for each requested CCX ID
    miss_cols = {}
    data_start = None
    for i, line in enumerate(lines):
        row = [c.strip() for c in line.split(",")]
        for ccx_id in ccx_ids:
            label = f"CCD (Aggregated)-{ccx_id}"
            if label in row:
                col = row.index(label)
                miss_cols[ccx_id] = col + L3_MISS_RATE_OFFSET
        if miss_cols and row[0] == "Timestamp":
            data_start = i + 1
            break

    if not miss_cols or data_start is None:
        return []

    results = []
    for line in lines[data_start:]:
        row = [c.strip() for c in line.split(",")]
        if not row[0] or not row[0][0].isdigit():
            break
        rates = [float(row[col]) for col in miss_cols.values() if col < len(row) and row[col]]
        if not rates:
            continue
        abs_ts = relative_to_absolute(row[0], profile_time)
        avg_rate = sum(rates) / len(rates)
        phase = get_phase(abs_ts, phases)
        results.append((abs_ts, avg_rate, phase))
    return results


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <cpu_id|start-end> [...]")
        print(f"  e.g. {sys.argv[0]} 28-39 121-123 5")
        sys.exit(1)

    cpu_ids = parse_cpu_args(sys.argv[1:])

    with open(CSV_PATH) as f:
        lines = f.readlines()

    cpu_to_ccx = parse_topology(lines)
    profile_time = parse_profile_time(lines)
    phases = parse_phases(PHASE_PATH)

    missing = [c for c in cpu_ids if c not in cpu_to_ccx]
    if missing:
        print(f"Warning: CPU IDs not found in topology: {missing}")

    ccx_ids = sorted({cpu_to_ccx[c] for c in cpu_ids if c in cpu_to_ccx})
    if not ccx_ids:
        print("No valid CCX IDs found. Exiting.")
        sys.exit(1)

    print(f"CPU IDs -> CCX IDs: {ccx_ids}")

    rates = parse_l3_miss_rates_avg(lines, ccx_ids, profile_time, phases)

    ccx_ids_str = ";".join(str(c) for c in ccx_ids)
    rows = [
        {"timestamp": abs_ts.isoformat(), "l3_missrate": round(avg, 4), "stage_info": phase, "ccx_ids": ccx_ids_str}
        for abs_ts, avg, phase in rates
    ]

    with open(ZEN_L3_MISS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "l3_missrate", "stage_info", "ccx_ids"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Written {len(rows)} rows to {ZEN_L3_MISS_PATH}")


if __name__ == "__main__":
    main()
