"""Make every report chart from the REAL numbers measured in the tests.

Run:   python make_charts.py        (charts are saved in the 'charts' folder)

Every list below says which test and which screenshot the numbers come from.
If you repeat a test, change the numbers here and run the script again.
"""
import os
import matplotlib
matplotlib.use("Agg")          # save to files, no pop-up windows
import matplotlib.pyplot as plt
import numpy as np

OUT = "charts"
os.makedirs(OUT, exist_ok=True)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name), dpi=200)
    plt.close(fig)
    print("saved", os.path.join(OUT, name))


def grouped_bars(ax, labels, series, names, fmt="%.1f", width=0.8):
    """Draw several bars side by side for each label."""
    x = np.arange(len(labels))
    w = width / len(series)
    for i, (vals, name) in enumerate(zip(series, names)):
        bars = ax.bar(x + (i - (len(series) - 1) / 2) * w, vals, w, label=name)
        ax.bar_label(bars, fmt=fmt, padding=2, fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)


# ---------- Chart 1: jitter per stream (Test 4, two sources, no loss) ----------
# Source: test04 rtp-streams-table.png (Wireshark RTP Streams, Mean/Max Jitter, ms)
streams = ["Client 440 Hz", "Client 660 Hz", "Mixer output"]
mean_jitter = [0.477, 0.429, 0.537]
max_jitter = [2.014, 1.268, 1.351]
fig, ax = plt.subplots(figsize=(7, 4.5))
grouped_bars(ax, streams, [mean_jitter, max_jitter], ["Mean jitter", "Max jitter"], "%.2f")
ax.set_ylabel("Jitter (ms)")
ax.set_ylim(0, 2.5)
ax.set_title("Jitter per stream, two sources, no loss (Test 4)")
ax.legend()
save(fig, "chart1_jitter.png")

# ---------- Chart 2: packet loss before and after (Test 4 vs Test 5) ----------
# Source: test04 rtp-streams-table.png (no loss set) and test05 rtp-table.png (5% set)
# In Test 5 the lossy sender lost 32 of 500 packets = 6.4% (the drop is random).
labels = ["Lossy client", "Clean client", "Mixer output"]
before = [0.0, 0.0, 0.0]
after = [6.4, 0.0, 0.0]
fig, ax = plt.subplots(figsize=(7, 4.5))
grouped_bars(ax, labels, [before, after],
             ["Test 4 (no loss set)", "Test 5 (5% loss set)"], "%.1f%%")
ax.set_ylabel("Packets lost (%)")
ax.set_ylim(0, 8)
ax.set_title("Packet loss measured by Wireshark")
ax.legend()
save(fig, "chart2_loss.png")

# ---------- Chart 3: number of sources in the mix over time (Test 4) ----------
# Source: test04 rtp-streams-table.png start times and durations:
#   660 Hz client starts at 0.00 s and lasts 9.98 s
#   440 Hz client starts at 1.27 s and lasts 9.98 s (ends at 11.25 s)
t = [0, 1.27, 9.98, 11.25]
n = [1, 2, 1, 0]
fig, ax = plt.subplots(figsize=(7, 4.5))
ax.step(t, n, where="post", linewidth=3)
ax.set_xlabel("Time since the first source started (s)")
ax.set_ylabel("Sources in the mix (CSRC count)")
ax.set_yticks([0, 1, 2, 3])
ax.set_ylim(0, 3)
ax.set_xlim(0, 12)
ax.set_title("Contributing sources in the mixed stream (Test 4)")
ax.grid(alpha=0.3)
save(fig, "chart3_sources.png")

# ---------- Chart 4: mixer delay for each jitter buffer size (Test 12) ----------
# Source: test12 mixer report screenshots, columns 'avg ms' and 'max ms'
buffers = ["20 ms", "60 ms", "120 ms"]
avg_delay = [14.4, 40.2, 101.5]
max_delay = [30.6, 71.5, 113.6]
fig, ax = plt.subplots(figsize=(7, 4.5))
grouped_bars(ax, buffers, [avg_delay, max_delay], ["Average delay", "Worst delay"])
ax.set_xlabel("Jitter buffer size")
ax.set_ylabel("Time a packet waits in the mixer (ms)")
ax.set_ylim(0, 135)
ax.set_title("Mixer delay grows with the jitter buffer (Test 12)")
ax.legend()
save(fig, "chart4_mixer_delay.png")

# ---------- Chart 5: late packets for each buffer size (Test 8 rerun) ----------
# Source: test08-rerun mixer reports, column 'late' (mic row and tone row)
mic_late = [4, 10, 0]       # live mic, about 2200 / 1700 / 1600 packets per run
tone_late = [10, 0, 0]      # 440 Hz tone, 500 packets per run
fig, ax = plt.subplots(figsize=(7, 4.5))
grouped_bars(ax, buffers, [mic_late, tone_late], ["Live microphone", "440 Hz tone"], "%d")
ax.set_xlabel("Jitter buffer size")
ax.set_ylabel("Late packets (dropped)")
ax.set_ylim(0, 13)
ax.set_title("Late packets for each jitter buffer size (Test 8 rerun)")
ax.legend()
save(fig, "chart5_late_packets.png")

# ---------- Chart 6: synchronization error (Test 13) ----------
# Source: test13 sync-test-20 / -60 / -120 screenshots, column 'error ms'
cases = ["0 ms\nno jitter", "0 ms\n30 ms jitter", "100 ms\nno jitter",
         "100 ms\n30 ms jitter", "250 ms\n30 ms jitter"]
err_20 = [0, 0, 0, -20, 10]
err_60 = [0, 0, 0, 0, 10]
err_120 = [0, 0, 0, 0, 30]
fig, ax = plt.subplots(figsize=(8.5, 4.8))
grouped_bars(ax, cases, [err_20, err_60, err_120],
             ["20 ms buffer", "60 ms buffer", "120 ms buffer"], "%d", width=0.75)
ax.axhspan(-20, 20, color="grey", alpha=0.12, label="One packet (20 ms)")
ax.axhline(0, color="black", linewidth=0.8)
ax.set_xlabel("Intended offset between the two sources, and network jitter")
ax.set_ylabel("Error = measured - intended (ms)")
ax.set_ylim(-35, 40)
ax.set_title("Synchronization error of two sources in the mix (Test 13)")
ax.legend(fontsize=8, ncol=2)
save(fig, "chart6_sync_error.png")

# ---------- Chart 7: loss at 0%, 5% and 10% (Test 11) ----------
# Source: test11 client playout reports
sets = ["0% set", "5% set", "10% set"]
dropped = [0, 21, 52]
detected = [0, 21, 52]
silence = [0, 21, 51]
fig, ax = plt.subplots(figsize=(7, 4.5))
grouped_bars(ax, sets, [dropped, detected, silence],
             ["Dropped on purpose", "Detected as lost", "Filled with silence"], "%d")
ax.set_ylabel("Packets (out of about 500)")
ax.set_ylim(0, 62)
ax.set_title("The client detects and conceals every lost packet (Test 11)")
ax.legend()
save(fig, "chart7_loss_test.png")

# ---------- Chart 8: scaling with 2, 4, 6 and 8 clients (Test 14) ----------
# Source: test14 mixer summaries ('mixer delay: average', 'CPU', 'packets per second')
clients = [2, 4, 6, 8]
delay = [53.7, 50.4, 52.3, 53.8]
cpu = [2.9, 8.5, 7.2, 10.8]
pps = [97, 192, 283, 371]
fig, axes = plt.subplots(1, 3, figsize=(12, 3.9))
axes[0].plot(clients, delay, marker="o", linewidth=2)
axes[0].set_ylim(0, 70)
axes[0].set_ylabel("Average mixer delay (ms)")
axes[0].set_title("Delay stays flat")
axes[1].plot(clients, cpu, marker="o", linewidth=2, color="tab:orange")
axes[1].set_ylim(0, 14)
axes[1].set_ylabel("CPU (% of one core)")
axes[1].set_title("CPU stays low")
axes[2].plot(clients, pps, marker="o", linewidth=2, color="tab:green")
axes[2].set_ylim(0, 420)
axes[2].set_ylabel("Packets sent per second")
axes[2].set_title("Packets grow in a straight line")
for ax in axes:
    ax.set_xlabel("Number of clients")
    ax.set_xticks(clients)
    ax.grid(alpha=0.3)
fig.suptitle("Scaling with the number of clients (Test 14, 0 lost and 0 late in every run)")
save(fig, "chart8_scaling.png")

# ---------- Chart 9: jitter of every stream in Tests 4, 7 and 8 (Test 6) ----------
# Test 6 had no run of its own: the jitter is read from the RTP Streams tables of
# Tests 4, 7 and 8 (columns Mean Jitter and Max Jitter, in ms). Order: top to bottom.
rows = [   # (label, mean, max, kind)
    ("T4  440 Hz client -> mixer", 0.476980, 2.014331, "client"),
    ("T4  660 Hz client -> mixer", 0.428852, 1.267726, "client"),
    ("T4  mixer output",           0.536696, 1.351464, "mixer"),
    ("T7  client 0x19b80900 -> mixer", 0.644931, 2.507524, "client"),
    ("T7  client 0xbabd8876 -> mixer", 0.513462, 2.133026, "client"),
    ("T7  client 0x4aaece8b -> mixer", 0.649826, 2.606977, "client"),
    ("T7  mixer -> client 0x19b80900", 0.292836, 0.751954, "mixer"),
    ("T7  mixer -> client 0xbabd8876", 0.281967, 0.745982, "mixer"),
    ("T7  mixer -> client 0x4aaece8b", 0.261971, 0.714607, "mixer"),
    ("T8  tone client -> mixer",   0.301320, 0.650484, "client"),
    ("T8  mixer -> tone client",   0.588782, 5.675598, "mixer"),
    ("T8  mixer -> mic client",    0.261192, 0.742785, "mixer"),
    ("T8  live mic -> mixer",      19.772662, 23.056436, "mic"),
]
colors = {"client": "tab:blue", "mixer": "tab:orange", "mic": "tab:red"}
fig, ax = plt.subplots(figsize=(9, 6))
y = np.arange(len(rows))[::-1]
ax.barh(y, [r[1] for r in rows], color=[colors[r[3]] for r in rows], label="_nolegend_")
ax.scatter([r[2] for r in rows], y, color="black", marker="D", s=22, zorder=3)
for yi, r in zip(y, rows):
    ax.text(r[1] * 1.08, yi + 0.28, f"{r[1]:.2f}", va="center", fontsize=7)
ax.set_yticks(y)
ax.set_yticklabels([r[0] for r in rows], fontsize=8)
ax.set_xscale("log")
ax.set_xlim(0.1, 60)
ax.set_xlabel("Jitter (ms, log scale)   bars = mean, black diamonds = max")
ax.set_title("Jitter of every stream in Tests 4, 7 and 8 (Test 6)")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=colors["client"], label="Steady client (tone)"),
                   Patch(color=colors["mixer"], label="Mixer output"),
                   Patch(color=colors["mic"], label="Live microphone")],
          loc="upper right", fontsize=8)
ax.grid(axis="x", alpha=0.3)
save(fig, "chart9_jitter_all_tests.png")

print("Done. 9 charts are in the folder:", OUT)