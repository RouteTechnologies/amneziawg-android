#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Runs inside the emulator started by reactivecircus/android-emulator-runner (see
# .github/workflows/emulator.yml). MODE: tests | screenshots | both (default tests).
#
#   tests        :ui:connectedDebugAndroidTest (instrumented smoke tests)
#   screenshots  install the debug APK, start the app and save real screenshots of the start page,
#                the "add tunnel" sheet and the tunnel editor to $SHOT_DIR (default build/screenshots)
#
# Uses only adb, uiautomator and python3; no extra dependencies.
set -euo pipefail

MODE="${MODE:-tests}"
PKG="${APP_PACKAGE:-io.routedns.awg.debug}"
ACTIVITY="org.amnezia.awg.activity.MainActivity"
OUT="${SHOT_DIR:-build/screenshots}"
API="$(adb shell getprop ro.build.version.sdk | tr -d '\r')"
GRADLE_FLAGS=(--no-daemon --stacktrace --max-workers=2 -Dorg.gradle.parallel=false)

run_tests() {
  ./gradlew "${GRADLE_FLAGS[@]}" :ui:connectedDebugAndroidTest
}

shot() {  # shot <name>
  local file="${OUT}/api${API}-$1.png"
  adb exec-out screencap -p > "${file}"
  [[ "$(stat -c %s "${file}")" -gt 2000 ]] || { echo "::error::screenshot ${file} is empty"; return 1; }
  echo "saved ${file} ($(stat -c %s "${file}") bytes)"
}

# tap_node <attribute> <value>: find a node in the current UI hierarchy and tap its centre.
tap_node() {
  adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1
  adb pull /sdcard/window.xml "${OUT}/window.xml" >/dev/null
  local xy
  xy="$(python3 -I - "${OUT}/window.xml" "$1" "$2" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, attr, value = sys.argv[1:4]
for node in ET.parse(path).iter("node"):
    actual = node.get(attr, "")
    if actual == value or (attr == "resource-id" and actual.endswith("/" + value)):
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds")))
        print((x1 + x2) // 2, (y1 + y2) // 2)
        break
PY
)"
  if [[ -z "${xy}" ]]; then
    echo "::warning::UI element ${1}=${2} not found"; return 1
  fi
  adb shell input tap ${xy}
}

take_screenshots() {
  mkdir -p "${OUT}"
  ./gradlew "${GRADLE_FLAGS[@]}" :ui:installDebug
  adb shell pm clear "${PKG}" >/dev/null 2>&1 || true   # fresh state: no tunnels
  adb shell input keyevent KEYCODE_HOME
  adb shell am start -W -n "${PKG}/${ACTIVITY}" >/dev/null
  sleep 6
  shot 01-start-page
  # The next screens are best effort: a missing element must not fail the run.
  if tap_node resource-id create_fab; then
    sleep 2; shot 02-add-tunnel-sheet
    if tap_node text "Create from scratch"; then
      sleep 3; shot 03-create-tunnel
    fi
  fi
  rm -f "${OUT}/window.xml"
  {
    echo "device: API ${API}, $(adb shell getprop ro.product.model | tr -d '\r')"
    echo "screen: $(adb shell wm size | tr -d '\r')"
    echo "app: ${PKG}"
  } > "${OUT}/device.txt"
}

case "${MODE}" in
  tests)       run_tests ;;
  screenshots) take_screenshots ;;
  both)        take_screenshots; run_tests ;;
  *) echo "::error::unknown MODE ${MODE}"; exit 1 ;;
esac
