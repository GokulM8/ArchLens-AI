#!/bin/sh
# Remove macOS AppleDouble ("._*") metadata files from the repository.
#
# macOS creates a ._<name> file beside every file it writes on FAT/exFAT
# volumes. They break git pack lookups (".git/objects/pack/._pack-*.idx:
# non-monotonic index") and Docker builds ("failed to xattr ... ._*").
# Only files carrying the AppleDouble magic (0x00051607) are deleted.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)

if command -v dot_clean >/dev/null 2>&1; then
  dot_clean -m "$root" || true
fi

find "$root" -name '._*' -type f | while IFS= read -r f; do
  if [ "$(head -c 4 "$f" | od -An -tx1 | tr -d ' \n')" = "00051607" ]; then
    rm -f "$f"
  else
    echo "kept (not AppleDouble): $f" >&2
  fi
done
echo "remaining ._ files: $(find "$root" -name '._*' | wc -l | tr -d ' ')"
