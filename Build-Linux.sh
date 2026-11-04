#!/usr/bin/env bash
# v0.4.3: original production-workflow parity included in CTest
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$root/migration/controller.py" verify
cmake -S "$root/harness" -B "$root/build-linux" -DCMAKE_BUILD_TYPE=Release
cmake --build "$root/build-linux" -j 4
ctest --test-dir "$root/build-linux" --output-on-failure
python3 "$root/migration/controller.py" verify
