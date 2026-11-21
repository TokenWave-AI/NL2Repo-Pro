"""Summarize Harbor runs on NL2Repo-Pro in the format of the paper's main table.

    python scripts/summarize.py jobs [more job folders]

For each system (agent and model) it reports, over the tasks it was scored on: the feature
score (mean reward), the test pass rate, the number of tasks with every feature accepted, and
the feature score per language. When a task was run more than once, the earliest scored trial
counts, as in the paper. Below the table, the paper's systems are scored on the same tasks.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

LANGS = ["python", "go", "rust", "java", "javascript"]
PAPER = Path(__file__).resolve().parent.parent / "results" / "paper-v1.tsv"


def load_trials(roots):
    """Yield (system, task, started_at, score or None) for every trial under the given folders."""
    for root in roots:
        for result_path in sorted(Path(root).rglob("result.json")):
            result = json.loads(result_path.read_text())
            if "task_name" not in result:
                continue  # a job-level result.json
            agent = (result.get("agent_info") or {}).get("name") or result["config"]["agent"]["name"]
            model = result["config"]["agent"].get("model_name")
            system = f"{agent} / {model}" if model else agent
            score_path = result_path.parent / "verifier" / "score.json"
            score = json.loads(score_path.read_text()) if score_path.exists() else None
            yield system, result["task_name"], result.get("started_at") or "", score


def summarize(scores, language):
    """scores: {task: (feature_score, test_pass_rate)} -> one table row as a list of strings."""
    far = [f for f, _ in scores.values()]
    tests = [t for _, t in scores.values() if t is not None]
    row = [str(len(scores)), pct(far), pct(tests), str(sum(1 for f in far if f >= 1 - 1e-9))]
    for lang in LANGS:
        row.append(pct([f for task, (f, _) in scores.items() if language.get(task) == lang]))
    return row


def pct(values):
    return f"{100 * sum(values) / len(values):.1f}" if values else "-"


def print_table(rows):
    header = ["System", "Tasks", "Feature score", "Test pass rate", "All features"] + [
        lang.capitalize() if lang != "javascript" else "JavaScript" for lang in LANGS]
    print("| " + " | ".join(header) + " |")
    print("|---|" + "--:|" * (len(header) - 1))
    for name, row in rows:
        print("| " + " | ".join([name] + row) + " |")


def main(roots):
    paper = list(csv.DictReader(PAPER.open(), delimiter="\t"))
    language = {r["instance_id"]: r["language"] for r in paper}

    first = {}      # (system, task) -> (started_at, score) of the earliest scored trial
    unscored = defaultdict(int)
    for system, task, started, score in load_trials(roots):
        if score is None:
            unscored[system] += 1
            continue
        key = (system, task)
        if key not in first or started < first[key][0]:
            first[key] = (started, score)

    by_system = defaultdict(dict)
    for (system, task), (_, score) in first.items():
        by_system[system][task] = (score["reward"], score.get("test_pass_ratio"))
    if not by_system:
        sys.exit("no scored trials found")

    print_table([(s, summarize(t, language)) for s, t in sorted(by_system.items())])
    for system, n in sorted(unscored.items()):
        print(f"\n{system}: {n} trial(s) without a score (agent or verifier error), not counted.")

    tasks = set().union(*by_system.values())
    reference = defaultdict(dict)
    for r in paper:
        if r["instance_id"] in tasks:
            reference[f'{r["model"]} (paper)'][r["instance_id"]] = (
                float(r["feature_score"]), float(r["test_pass_rate"]))
    print(f"\nThe paper's systems on the same {len(tasks)} task(s):\n")
    print_table([(s, summarize(t, language)) for s, t in reference.items()])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
