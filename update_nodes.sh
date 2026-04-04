#!/bin/bash
# Usage: ./update_nodes.sh [ips_file]
# Default: ips.txt

IPS_FILE="${1:-ips.txt}"
DASHBOARD="dashboard.html"

if [ ! -f "$IPS_FILE" ]; then
  echo "Error: $IPS_FILE not found"
  exit 1
fi

# Build the NODES array string from the IPs file (skip comments and blank lines)
NODES="const NODES = [\n"
while IFS= read -r line; do
  line="${line%%#*}"   # strip inline comments
  line="${line// /}"   # strip spaces
  [ -z "$line" ] && continue
  NODES+="  \"${line}:8764\",\n"
done < "$IPS_FILE"
NODES+="];"

# Replace the NODES block in dashboard.html
python3 - "$DASHBOARD" "$NODES" <<'EOF'
import sys, re

dashboard = sys.argv[1]
new_nodes = sys.argv[2]

with open(dashboard, "r", encoding="utf-8") as f:
    content = f.read()

# Replace from 'const NODES = [' to '];'
updated = re.sub(
    r'const NODES = \[.*?\];',
    new_nodes,
    content,
    flags=re.DOTALL
)

with open(dashboard, "w", encoding="utf-8") as f:
    f.write(updated)

print(f"Updated {dashboard} with nodes from {sys.argv[1]}")
EOF

echo "Done. IPs loaded from: $IPS_FILE"
