#!/bin/bash
# Process Juicebox citation batches one at a time.
# Usage: ./juicebox/run_batches.sh [start_batch]
#   start_batch: optional, resume from this batch number (default: 1)

set -a && source .env && set +a

cd "$(dirname "$0")/.."

START=${1:-1}
TOTAL=$(ls juicebox/batches/batch_*.csv 2>/dev/null | wc -l)

echo "Processing batches $START to $TOTAL"
echo "======================================"

for batch_file in juicebox/batches/batch_*.csv; do
    batch_num=$(echo "$batch_file" | grep -o '[0-9]\{3\}')
    batch_int=$((10#$batch_num))

    # Skip batches before start
    if [ "$batch_int" -lt "$START" ]; then
        continue
    fi

    output="juicebox/enriched/enriched_${batch_num}.csv"

    # Skip already-completed batches
    if [ -f "$output" ]; then
        echo "[Batch $batch_int/$TOTAL] Already complete, skipping"
        continue
    fi

    echo ""
    echo "======================================"
    echo "[Batch $batch_int/$TOTAL] Processing $batch_file"
    echo "======================================"

    python3 outreach_finder.py --client juicebox "$batch_file" "$output"

    if [ $? -ne 0 ]; then
        echo "[Batch $batch_int/$TOTAL] FAILED — stopping. Resume with: ./juicebox/run_batches.sh $batch_int"
        exit 1
    fi

    echo "[Batch $batch_int/$TOTAL] Done -> $output"
done

echo ""
echo "======================================"
echo "All batches complete! Merging..."
echo "======================================"

# Merge all enriched batches into one final file
python3 -c "
import csv, glob

files = sorted(glob.glob('juicebox/enriched/enriched_*.csv'))
all_rows = []
fieldnames = None

for f in files:
    with open(f, 'r', newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)
        if fieldnames is None:
            fieldnames = reader.fieldnames
        all_rows.extend(reader)

# Raw: everything
with open('juicebox/enriched/juicebox_enriched_final.csv', 'w', newline='', encoding='utf-8-sig') as fh:
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_rows)

# Clean: no skipped rows
clean = [r for r in all_rows if r.get('site_type', '') != 'Skipped']
with open('juicebox/enriched/juicebox_enriched_final_clean.csv', 'w', newline='', encoding='utf-8-sig') as fh:
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(clean)

print(f'Merged {len(all_rows)} rows -> juicebox/enriched/juicebox_enriched_final.csv')
print(f'Clean: {len(clean)} rows -> juicebox/enriched/juicebox_enriched_final_clean.csv')
print(f'Filtered out {len(all_rows) - len(clean)} skipped rows')
"
