#!/usr/bin/env bash
set -euo pipefail

NEXMON_CSI_DIR="${NEXMON_CSI_DIR:-$HOME/nexmon/patches/bcm43455c0/7_45_189/nexmon_csi}"
MAKECSIPARAMS_DIR="$NEXMON_CSI_DIR/utils/makecsiparams"
CHANNEL_SPEC="${CHANNEL_SPEC:-1/20}"
CORE_MASK="${CORE_MASK:-1}"
NSS_MASK="${NSS_MASK:-1}"
WLAN_IFACE="${CSI_INTERFACE:-wlan0}"

cd "$MAKECSIPARAMS_DIR"
PARAM=$(./makecsiparams -c "$CHANNEL_SPEC" -C "$CORE_MASK" -N "$NSS_MASK")
echo "PARAM=$PARAM"
echo "PARAM length=${#PARAM}"

cd "$NEXMON_CSI_DIR"
sudo timeout 5s nexutil -I"$WLAN_IFACE" -s500 -b -l34 -v"$PARAM"
echo "nexutil set exit=$?"

sudo nexutil -m1
nexutil -m
nexutil -k
