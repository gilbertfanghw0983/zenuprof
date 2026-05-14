# uprof L3 Miss Rate Extractor

Extracts per-CCX L3 miss rates from an AMD uProf Zen4 CSV report, annotates each sample with a workload phase, and writes the results to a CSV file.

## Requirements

- Python 3.6+
- No third-party dependencies

## Input Files

### uProf CSV (`uprof.csv`)

AMD uProf PCM report for a Zen4 processor (e.g. EPYC 9755). Must contain:
- `Profile Time:` header — used as the absolute start time
- `CPU Topology:` section — maps CPU IDs to CCX (CCD) IDs
- `L3 METRICS` section — per-CCD `L3 Miss %` samples with relative timestamps

### Phase CSV (`phase.csv`)

Workload phase definitions with three columns:

| Column | Description |
|---|---|
| `op` | Phase name (e.g. `ReadFilter`, `PerformEmbedding`) |
| `median_start_timestamp` | Phase start time in ISO 8601 format |
| `end_timestamp` | Phase end time in ISO 8601 format |

Example:
```
op,median_start_timestamp,end_timestamp
ReadFilter,2026-05-14T05:40:00.000,2026-05-14T05:40:45.228
PerformEmbedding,2026-05-14T05:40:54.228,2026-05-14T05:48:21.840
```

## Usage

```
python3 getl3miss.py <uprof.csv> <phase.csv> <output.csv> <cpu_range> [cpu_range ...]
```

CPU ranges can be individual IDs or hyphen-separated ranges:

```
python3 getl3miss.py l2_zen4_2.csv phase.csv l3missrate.csv 28-39 121-123 5
```

## Output

A CSV file with one row per uProf sample timestamp that falls within a known phase. Rows with no matching phase are dropped.

| Column | Description |
|---|---|
| `timestamp` | Absolute ISO 8601 timestamp (profile start + relative offset) |
| `l3_missrate` | Average L3 miss % across all CCX IDs derived from the input CPUs |
| `stage_info` | Workload phase name from `phase.csv` |

Example:
```
timestamp,l3_missrate,stage_info
2026-05-14T05:40:45.199000,19.98,ReadFilter
```

## How It Works

1. Parses the CPU topology section to map each CPU ID to its CCX (CCD) ID
2. Deduplicates CCX IDs across all specified CPU ranges
3. Converts each relative uProf timestamp to an absolute timestamp using the profile start time
4. For each timestamp, averages the `L3 Miss %` values across all resolved CCX IDs
5. Matches the absolute timestamp against phase windows and annotates accordingly
6. Drops samples that fall outside all defined phases
