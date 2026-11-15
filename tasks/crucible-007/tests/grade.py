"""Grade by replaying the sidecar's journal from the seed. Any journal the
rules could not have produced scores 0."""
import json
import sys

sys.path.insert(0, "/tests")
from crucible.episode import ActionError, replay  # noqa: E402

JOURNAL = "/var/crucible/journal.jsonl"
MAX_BYTES = 4 * 1024 * 1024


def main():
    seed, lab_budget = (int(v) for v in open("/tests/seed.txt").read().split())
    details = {"seed": seed, "lab_budget": lab_budget}
    reward = 0.0
    try:
        with open(JOURNAL, "rb") as f:
            raw = f.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ActionError("journal too large")
        journal = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        ep = replay(seed, journal, lab_budget=lab_budget)
        score = ep.score()
        reward = float(score["reward"])
        details.update(score)
        details["actions"] = len(journal)
    except FileNotFoundError:
        details["error"] = "journal not collected from the simulator"
    except (ActionError, ValueError, UnicodeDecodeError, RecursionError) as e:
        details["error"] = f"journal rejected: {e}"
    except Exception as e:  # never leave a partial reward behind
        details["error"] = f"grader failure: {type(e).__name__}"
    reward = min(1.0, max(0.0, reward)) if "error" not in details else 0.0
    with open("/logs/verifier/details.json", "w") as f:
        json.dump(details, f, indent=1)
    with open("/logs/verifier/reward.txt", "w") as f:
        f.write(f"{reward:.4f}\n")
    print(json.dumps(details, indent=1))


if __name__ == "__main__":
    main()
