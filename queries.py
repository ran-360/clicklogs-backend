import json
import os
from collections import defaultdict, Counter

import firebase_admin
from firebase_admin import credentials, firestore

#  Firebase init 
if not firebase_admin._apps:
    if os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
    else:
        key_dict = json.loads(os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
        cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()


def mean(values):
    return sum(values) / len(values) if values else 0


# ── Fetch all docs once ────────────────────────────────────────────────────────
print("Fetching data from Firestore...")
all_docs = [doc.to_dict() for doc in db.collection("tap_logs").stream()]
print(f"Total documents: {len(all_docs)}")

if not all_docs:
    print("No data in tap_logs collection.")
    exit()

# Show summary of what data exists
print(f"Platforms:       {Counter(d.get('platform') for d in all_docs)}")
print(f"InterfaceTypes:  {Counter(d.get('interfaceType') for d in all_docs)}")
print(f"Sessions:        {len(set(d.get('sessionId') for d in all_docs))} unique sessions")


#Mean tap duration — by platform 
def query_4a():
    print("\n── 4a: Mean Tap Duration by Platform ───────────────────────────")

    # Group by platform dynamically — works with any platform values in data
    platform_durations = defaultdict(list)
    for doc in all_docs:
        plat = doc.get("platform", "unknown")
        dur  = doc.get("duration", 0)
        platform_durations[plat].append(dur)

    for platform, durations in sorted(platform_durations.items()):
        print(f"  {platform.upper():12s}: "
              f"{len(durations):4d} taps | "
              f"mean = {mean(durations):7.2f} ms | "
              f"min = {min(durations):.0f} ms | "
              f"max = {max(durations):.0f} ms")

    # Comparison if both android and pc exist
    android = platform_durations.get("android", [])
    pc      = platform_durations.get("pc",      [])
    if android and pc:
        diff   = mean(android) - mean(pc)
        slower = "Android" if diff > 0 else "PC"
        print(f"\n  → {slower} users tap {abs(diff):.2f} ms slower on average")
    else:
        print(f"\n  → Collect data from both platforms to compare")


# Mean duration — feedbackshown vs nofeedback
def query_4b():
    print("\n── 4b: Mean Tap Duration by Interface Type ─────────────────────")

    # Group by interfaceType dynamically
    interface_durations = defaultdict(list)
    for doc in all_docs:
        itype = doc.get("interfaceType", "unknown")
        dur   = doc.get("duration", 0)
        interface_durations[itype].append(dur)

    for itype, durations in sorted(interface_durations.items()):
        print(f"  {itype:18s}: "
              f"{len(durations):4d} taps | "
              f"mean = {mean(durations):7.2f} ms")

    # Comparison
    fb  = interface_durations.get("feedbackshown", [])
    nfb = interface_durations.get("nofeedback",    [])

    if fb and nfb:
        diff      = mean(fb) - mean(nfb)
        direction = "slower" if diff > 0 else "faster"
        print(f"\n  → Feedback interface is {abs(diff):.2f} ms {direction} "
              f"than no-feedback")
        if diff > 0:
            print(f"  → Showing feedback may distract users, increasing tap time")
        else:
            print(f"  → Feedback helps users tap faster")
    else:
        print(f"\n  → Need data from both interface types to compare")
        print(f"  → Complete both interface variations (tap 50 times twice per session)")


# Sessions completing both interfaces vs dropping off
def query_4c():
    print("\n── 4c: Session Completion Rate ─────────────────────────────────")

    # Group by sessionId
    session_data = defaultdict(lambda: {
        "interfaceSequences": set(),
        "interfaceTypes":     set(),
        "platform":           "",
        "tapCounts":          defaultdict(int),
    })

    for doc in all_docs:
        sid = doc.get("sessionId", "unknown")
        session_data[sid]["interfaceSequences"].add(
            doc.get("interfaceSequence", 0))
        session_data[sid]["interfaceTypes"].add(
            doc.get("interfaceType", ""))
        session_data[sid]["platform"] = doc.get("platform", "unknown")
        session_data[sid]["tapCounts"][
            doc.get("interfaceSequence", 0)] += 1

    # Classify sessions
    completed_both  = []
    dropped_after_1 = []

    for sid, data in session_data.items():
        if (1 in data["interfaceSequences"] and
                2 in data["interfaceSequences"]):
            completed_both.append((sid, data))
        else:
            dropped_after_1.append((sid, data))

    total = len(session_data)
    pct   = (len(completed_both) / total * 100) if total > 0 else 0

    print(f"  Total unique sessions:         {total}")
    print(f"  Completed both interfaces:     {len(completed_both)}")
    print(f"  Dropped off after first only:  {len(dropped_after_1)}")
    print(f"  Completion rate:               {pct:.1f}%")

    # Per session detail
    print("\n  Session details:")
    for sid, data in session_data.items():
        c1     = data["tapCounts"].get(1, 0)
        c2     = data["tapCounts"].get(2, 0)
        status = "✓ completed both" if (1 in data["interfaceSequences"] and
                                         2 in data["interfaceSequences"]) \
                                    else "✗ dropped after first"
        print(f"    [{data['platform']:8s}] "
              f"session {sid[:16]}... | "
              f"seq1={c1:2d} taps | "
              f"seq2={c2:2d} taps | "
              f"{status}")

    # Per-platform breakdown
    if total > 1:
        print("\n  Per-platform breakdown:")
        plat_complete = defaultdict(int)
        plat_drop     = defaultdict(int)

        for sid, data in completed_both:
            plat_complete[data["platform"]] += 1
        for sid, data in dropped_after_1:
            plat_drop[data["platform"]] += 1

        for plat in sorted(
                set(list(plat_complete.keys()) + list(plat_drop.keys()))):
            c   = plat_complete[plat]
            d   = plat_drop[plat]
            t   = c + d
            pct = (c / t * 100) if t > 0 else 0
            print(f"    {plat:10s}: {c} completed, "
                  f"{d} dropped ({pct:.0f}% completion)")


# Run all 
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  tap_logs Analytics")
    print("=" * 55)

    query_4a()
    query_4b()
    query_4c()

    print("\n" + "=" * 55)