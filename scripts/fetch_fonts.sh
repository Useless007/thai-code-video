#!/usr/bin/env bash
# Download OFL fonts into <dir> (default assets/fonts). Fails loudly on any missing file.
#
# The Thai set, chosen to fill the same roles the upstream Korean set filled.
# Every one of these ships Thai and Latin in the same file, which matters: a
# promo that mixes a Thai sentence with a Latin product name must not switch
# face mid-line.
set -euo pipefail
dir="${1:-assets/fonts}"; mkdir -p "$dir"
get() { curl -fsSL -o "$dir/$1" "$2" || { echo "font download failed: $1 <- $2" >&2; exit 1; }; echo "ok $1"; }
GF=https://github.com/google/fonts/raw/main/ofl

# Display — the heavy voice a title card is set in. Kanit is the Thai face with
# real weight range and a Latin companion that does not look borrowed.
get Kanit-ExtraBold.ttf "$GF/kanit/Kanit-ExtraBold.ttf"
get Kanit-Bold.ttf "$GF/kanit/Kanit-Bold.ttf"

# Body / UI.
get NotoSansThai.ttf "$GF/notosansthai/NotoSansThai%5Bwdth,wght%5D.ttf"
get IBMPlexSansThai-Regular.ttf "$GF/ibmplexsansthai/IBMPlexSansThai-Regular.ttf"
get IBMPlexSansThai-Bold.ttf "$GF/ibmplexsansthai/IBMPlexSansThai-Bold.ttf"

# Handwriting — the hand-drawn look. Thai handwriting faces are loop-less and
# informal; Charmonman is the closest to what a person writes on a whiteboard.
get Charmonman-Bold.ttf "$GF/charmonman/Charmonman-Bold.ttf"
get Sriracha-Regular.ttf "$GF/sriracha/Sriracha-Regular.ttf"

# Serif — the weight a claim is printed in.
get NotoSerifThai.ttf "$GF/notoserifthai/NotoSerifThai%5Bwdth,wght%5D.ttf"

# Monospace for the terminal look. Thai has no true monospace face with full
# tone-mark coverage, so the terminal look sets Thai in IBM Plex Sans Thai and
# code in a Latin mono. Mixing is the honest answer; faking a Thai mono by
# letter-spacing a proportional face breaks the marks.
get SpaceMono-Regular.ttf "$GF/spacemono/SpaceMono-Regular.ttf"

# Pixel. This is the one gap the Thai set cannot fill: there is no OFL Thai
# bitmap face with tone-mark coverage. The arcade and thermal looks therefore
# set their Thai in Kanit and keep the pixel face for Latin and numerals only —
# see references/thai.md. Do not set a Thai string in this font.
get PressStart2P-Regular.ttf "$GF/pressstart2p/PressStart2P-Regular.ttf"

# Latin companions kept from upstream for the looks that use them.
get Geist.ttf "$GF/geist/Geist%5Bwght%5D.ttf"
