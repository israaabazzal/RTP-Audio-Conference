"""Tidy the project folder. Safe to run more than once.

Run it INSIDE the project folder (next to mixer.py):
    python tidy_project.py

It does four things:
  1. moves the old mixer versions into 'old_versions' and gives them clear names
  2. removes the hard-coded microphone/speaker numbers (1, 3) from mic_test.py
     and record_wav.py (they belonged to your first computer)
  3. deletes the __pycache__ folders
  4. never touches venv, venv_new or any of your other files
"""
import os
import re
import shutil

MOVES = {                       # old name -> new name inside old_versions
    "mixer_old.py": "mixer_v1a_single_destination.py",
    "mixer-oldd.py": "mixer_v1b_clients_mode.py",
    "mixer-before-jitter.py": "mixer_v2_mixminus.py",
    "mixer_v2_jitter.py": "mixer_v3_jitter.py",
    "mixer_v4_delay.py": "mixer_v4_delay.py",
}
DEVICE_FILES = ["mic_test.py", "record_wav.py"]
DEVICE_LINE = re.compile(r"^(\s*)sd\.default\.device\s*=.*$")
NOTE = ("# To use a specific microphone/speaker, set: sd.default.device = (input, output)\n"
        "# (list the numbers with: python -c \"import sounddevice; print(sounddevice.query_devices())\")")

if not os.path.exists("mixer.py"):
    raise SystemExit("Run this script inside the project folder (the one that contains mixer.py).")

print("1. Old mixer versions")
os.makedirs("old_versions", exist_ok=True)
for old, new in MOVES.items():
    target = os.path.join("old_versions", new)
    if os.path.exists(old) and not os.path.exists(target):
        shutil.move(old, target)
        print(f"   moved {old} -> old_versions/{new}")
    elif os.path.exists(target):
        print(f"   already done: old_versions/{new}")
    else:
        print(f"   not found (skipped): {old}")
readme = os.path.join("old_versions", "README.txt")
if not os.path.exists(readme):
    with open(readme, "w", encoding="utf-8") as f:
        f.write("Earlier versions of mixer.py, kept to show how the mixer evolved.\n\n"
                "v1a  mixer_v1a_single_destination.py  one full mix to ONE address (first version)\n"
                "v1b  mixer_v1b_clients_mode.py         sends the same full mix to every client, own voice included\n"
                "v2   mixer_v2_mixminus.py              mix-minus: each client gets a mix without its own voice\n"
                "v3   mixer_v3_jitter.py                per-source jitter buffer ordered by RTP timestamp\n"
                "v4   mixer_v4_delay.py                 also records how long each packet waits in the mixer\n"
                "v5   mixer.py (main folder)            adds the summary: CPU and packets per second\n\n"
                "Which version produced which evidence:\n"
                "  v2  Tests 3, 4, 5, 7 and 8 (first runs), and Test 11 (done before the jitter buffer)\n"
                "  v3  Test 7 rerun and the Test 8 buffer-size comparison\n"
                "  v4  Tests 9, 10, 12 and 13\n"
                "  v5  Test 14\n\n"
                "To run one of these, copy it next to rtp.py in the main folder first.\n")
    print("   wrote old_versions/README.txt")

print("2. Hard-coded audio device numbers")
for name in DEVICE_FILES:
    if not os.path.exists(name):
        print(f"   not found (skipped): {name}")
        continue
    with open(name, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(eol)
    changed = False
    out = []
    for line in lines:
        m = DEVICE_LINE.match(line)
        if m:
            indent = m.group(1)
            for note_line in NOTE.split("\n"):
                out.append(indent + note_line)
            changed = True
        else:
            out.append(line)
    if changed:
        with open(name, "w", encoding="utf-8", newline="") as f:
            f.write(eol.join(out))
        print(f"   fixed {name}")
    else:
        print(f"   nothing to change in {name}")

print("3. __pycache__ folders")
removed = 0
for folder in [".", "old_versions"]:
    p = os.path.join(folder, "__pycache__")
    if os.path.isdir(p):
        shutil.rmtree(p)
        removed += 1
print(f"   removed {removed}")

print("\nDone. The venv and venv_new folders were NOT touched.")
print("Next: run  python make_submission_zip.py  when you want the zip to hand in.")