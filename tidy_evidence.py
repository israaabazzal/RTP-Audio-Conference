"""Give the evidence folders and screenshots clear, consistent names.

Run it from the folder that CONTAINS the 'evidence' folder (or from inside it):
    python tidy_evidence.py

It first shows exactly what it will rename and waits for you to press Enter.
Only the names it knows are renamed. Everything else is left alone and listed.
It also creates 'captures' (put your .pcapng files there) and 'charts'.
"""
import os

RENAMES = {
    "test01_rtp_unit": ("test01_rtp_unit", {}),
    "test02_single_packet": ("test02_single_packet", {}),
    "test03_rtp_streams": ("test03_one_source", {
        "One packet opened.png": "one_packet_opened.png",
        "client-window.png": "client_window.png",
        "mixer-wimdow.png": "mixer_window.png",
        "rtp-streams-table.png": "rtp_streams_table.png",
    }),
    "test04-2client": ("test04_two_sources", {
        "RTP Stream Analysis graph.png": "rtp_stream_analysis_graph.png",
        "client-window-440.png": "client_window_440.png",
        "client-window-660.png": "client_window_660.png",
        "mixer-csrc=1.png": "mixer_packet_csrc1.png",
        "mixer-csrc=2.png": "mixer_packet_csrc2.png",
        "mixer-window-2client.png": "mixer_window.png",
        "rtp-streams-table.png": "rtp_streams_table.png",
    }),
    "test05-Packet-loss-(5%)": ("test05_packet_loss_5pct", {
        "Screen Recording 2026-11-03 052416.mp4": "screen_recording.mp4",
        "loss graph.png": "loss_graph.png",
        "mixer-window.png": "mixer_window.png",
        "rtp-table.png": "rtp_streams_table.png",
    }),
    "test07-3clients": ("test07_three_clients", {
        "61795.png": "mixer_packet_to_port_61795.png",
        "64644.png": "mixer_packet_to_port_64644.png",
        "64645.png": "mixer_packet_to_port_64645.png",
        "client-window-440.png": "client_window_440.png",
        "client-window-660.png": "client_window_660.png",
        "client-window-880.png": "client_window_880.png",
        "mixer-wimdow.png": "mixer_window.png",
        "rtp-streams-table.png": "rtp_streams_table.png",
    }),
    "test07-rerun-with-jitter": ("test07_rerun_with_jitter_buffer", {
        "mixer-window-jitter.png": "mixer_report_3_clients.png",
    }),
    "test08-live-mic": ("test08_live_mic", {
        "client2-window.png": "tone_client_window.png",
        "live-mic-tone.png": "mixer_packet_to_tone_client_csrc_mic.png",
        "live-mic-window.png": "mic_client_window.png",
        "mixer-window-part1.png": "mixer_window_part1.png",
        "mixer-window-part2.png": "mixer_window_part2.png",
        "rtp-streams-table.png": "rtp_streams_table.png",
        "the-tone-client.png": "mixer_packet_to_mic_client_csrc_tone.png",
    }),
    "test08-rerun-with-jitter": ("test08_rerun_buffer_sizes", {
        "mixer-window-jitter-20ms.png": "buffer_20ms_log_and_report.png",
        "mixer-window-jitter-60ms-p1.png": "buffer_60ms_log_start.png",
        "mixer-window-jitter-60ms.png": "buffer_60ms_log_and_report.png",
        "mixer-window-jitter-120ms.png": "buffer_120ms_log.png",
        "mixer-window-jitter-120ms-p2.png": "buffer_120ms_report.png",
    }),
    "test09-Late-join-and-early-leave": ("test09_late_join_early_leave", {
        "B-listen-to-A.png": "b_hears_a_csrc1_first_packet.png",
        "B-listen-to-A-C.png": "b_hears_a_and_c_csrc2.png",
        "B-listen-to-C.png": "b_hears_c_csrc1_last_packet.png",
        "mixer-window.png": "mixer_window_and_report.png",
    }),
    "Test10-4-or-more-clients": ("test10_four_clients", {
        "client1.png": "mixer_packet_to_port_50595_csrc3.png",
        "client2.png": "mixer_packet_to_port_59204_csrc3.png",
        "mixer-window.png": "mixer_window_and_report.png",
        "rtp-streams-table.png": "rtp_streams_table.png",
    }),
    "test11-Loss at 0%, 5% and 10%": ("test11_loss_0_5_10pct", {
        "0loss.png": "loss_0pct_client_report.png",
        "5%loss.png": "loss_5pct_client_report.png",
        "10%loss.png": "loss_10pct_client_report.png",
    }),
    "test12-Latency": ("test12_latency", {
        "20ms.png": "mixer_report_buffer_20ms.png",
        "60ms.png": "mixer_report_buffer_60ms.png",
        "120ms.png": "mixer_report_buffer_120ms.png",
        "60ms-test1.png": "wireshark_seq100_60ms.png",
        "60ms-test2.png": "wireshark_seq200_60ms.png",
        "60ms-test3.png": "wireshark_seq300_60ms.png",
    }),
    "test13-synchronization": ("test13_synchronization", {
        "mixer-window-20.png": "mixer_report_buffer_20ms.png",
        "mixer-window-60.png": "mixer_report_buffer_60ms.png",
        "mixer-window-120.png": "mixer_report_buffer_120ms.png",
        "sync-test-20.png": "sync_table_buffer_20ms.png",
        "sync-test-60.png": "sync_table_buffer_60ms.png",
        "sync-test-120.png": "sync_table_buffer_120ms.png",
        "Screenshot 2026-11-03 092851.png": "wireshark_waveform_60ms.png",
    }),
    "test14_scaling": ("test14_scaling", {
        "scaling-4-clients.png": "scaling_4_clients.png",
        "report-6-client.png": "scaling_6_clients_report.png",
        "report-8-client.png": "scaling_8_clients_report.png",
    }),
}

if os.path.isdir("evidence"):
    base = "evidence"
elif os.path.basename(os.path.abspath(".")) == "evidence":
    base = "."
else:
    raise SystemExit("I can't find the 'evidence' folder. Run this from the folder that contains it.")

plan = []        # (old path, new path)
unknown = []
for folder in sorted(os.listdir(base)):
    fpath = os.path.join(base, folder)
    if not os.path.isdir(fpath) or folder in ("captures", "charts"):
        continue
    if folder not in RENAMES:
        unknown.append(fpath)
        continue
    new_folder, files = RENAMES[folder]
    for name in sorted(os.listdir(fpath)):
        if name in files:
            plan.append((os.path.join(fpath, name), os.path.join(fpath, files[name])))
        else:
            unknown.append(os.path.join(fpath, name))
    if new_folder != folder:
        plan.append((fpath, os.path.join(base, new_folder)))

if not plan:
    print("Nothing to rename. (Already done?)")
else:
    print("I will rename:")
    for old, new in plan:
        print(f"  {os.path.relpath(old, base)}\n      -> {os.path.relpath(new, base)}")
    if unknown:
        print("\nI will leave these alone (not in my list):")
        for u in unknown:
            print("  ", os.path.relpath(u, base))
    input("\nPress Enter to rename, or Ctrl+C to cancel... ")
    # rename files first, then folders (so the paths above stay valid)
    for old, new in plan:
        if os.path.isfile(old):
            os.rename(old, new)
    for old, new in plan:
        if os.path.isdir(old):
            os.rename(old, new)
    print("Renamed.")

os.makedirs(os.path.join(base, "captures"), exist_ok=True)
print("\nThe folder 'captures' is ready: copy your .pcapng files into it.")
print("Suggested names: test03_one_source.pcapng, test04_two_sources.pcapng, test05_loss5pct.pcapng,")
print("test07_three_clients.pcapng, test08_live_mic.pcapng, test09_late_join_leave.pcapng,")
print("test10_four_clients.pcapng, test12_latency_60ms.pcapng, test13_sync.pcapng")
