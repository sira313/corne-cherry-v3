#!/usr/bin/env bash
# Pantau baterai Corne kiri melalui BlueZ/UPower dan simpan log CSV.
# Angka 100% hanya dijadikan titik awal setelah pengguna mengonfirmasi LED
# charging sudah mati.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
INTERVAL="${INTERVAL:-60}"
LOG="${BATTERY_LOG:-$ROOT/battery-left.csv}"
DEVICE="${UPower_DEVICE:-}"

usage() {
    cat <<'EOF'
Usage: ./battery-left.sh [options]

Options:
  --list                 tampilkan device UPower yang memiliki baterai
  --device PATH          pilih device UPower secara eksplisit
  --interval SECOND      jarak pembacaan (default: 60)
  --log FILE             file CSV (default: battery-left.csv)
  -h, --help             bantuan

Contoh:
  ./battery-left.sh --list
  ./battery-left.sh --interval 300
EOF
}

command -v upower >/dev/null || {
    echo "Error: perintah 'upower' belum terpasang." >&2
    exit 1
}

while (($#)); do
    case "$1" in
        --list) upower -e | while read -r d; do
            info="$(upower -i "$d" 2>/dev/null || true)"
            # Tampilkan keyboard Bluetooth saja; jangan tampilkan BAT0 atau
            # DisplayDevice milik laptop yang juga diekspos oleh UPower.
            if grep -q '^  keyboard$' <<<"$info" &&
               grep -q '^    percentage:' <<<"$info"; then
                printf '%s\n' "$d"
                grep -E '^    (model|percentage|state):' <<<"$info" || true
            fi
        done; exit 0 ;;
        --device) DEVICE="${2:?--device membutuhkan PATH}"; shift 2 ;;
        --interval) INTERVAL="${2:?--interval membutuhkan angka}"; shift 2 ;;
        --log) LOG="${2:?--log membutuhkan nama file}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Argumen tidak dikenal: $1" >&2; usage >&2; exit 1 ;;
    esac
done

if [[ -z "$DEVICE" ]]; then
    mapfile -t candidates < <(upower -e | while read -r d; do
        info="$(upower -i "$d" 2>/dev/null || true)"
        if grep -qiE 'corne|nice.?nano' <<<"$info" && grep -q '^    percentage:' <<<"$info"; then
            echo "$d"
        fi
    done)
    if ((${#candidates[@]} == 1)); then
        DEVICE="${candidates[0]}"
    else
        echo "Device Corne tidak terpilih otomatis. Daftar device:" >&2
        upower -e >&2
        echo "Jalankan --list lalu gunakan --device PATH." >&2
        exit 1
    fi
fi

read_battery() {
    upower -i "$DEVICE" | awk '/^[[:space:]]*percentage:/ {print $2; exit}'
}

mkdir -p "$(dirname "$LOG")"
if [[ ! -e "$LOG" ]]; then
    printf 'timestamp,device,percentage,elapsed_since_full_seconds,notes\n' > "$LOG"
fi

echo "Device: $DEVICE"
read -r -p "Pastikan charging LED kiri SUDAH MATI. Jadikan kondisi ini 100% penuh? [y/N] " answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
    full_epoch="$(date +%s)"
    echo "Titik awal penuh disimpan. Monitoring tiap ${INTERVAL}s; Ctrl-C untuk berhenti."
else
    full_epoch=""
    echo "Tanpa titik awal full; log tetap berjalan."
fi

while :; do
    now="$(date +%s)"
    timestamp="$(date --iso-8601=seconds)"
    percentage="$(read_battery || true)"
    [[ -n "$percentage" ]] || percentage="unknown"
    elapsed=""
    [[ -n "$full_epoch" ]] && elapsed=$((now - full_epoch))
    printf '%s,%s,%s,%s,%s\n' "$timestamp" "$DEVICE" "$percentage" "$elapsed" "" >> "$LOG"
    printf '\r%s  %s  %s%%  elapsed full: %s' "$timestamp" "$DEVICE" "$percentage" "${elapsed:-n/a}"
    sleep "$INTERVAL"
done
