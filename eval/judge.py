# LLM-as-judge scorer. Sends each agent turn to the larger model and scores it
# on policy compliance, helpfulness, and correctness. Run after the script evaluator.

from llm import judge as llm_judge
from prompts import JUDGE_TURN


def score_transcript(transcript: list[dict]) -> dict:
    turn_scores = []
    history_lines = []

    for turn in transcript:
        history_str = (
            "\n".join(
                f"{'User' if t['role'] == 'user' else 'Agent'}: {t['content']}"
                for t in history_lines[-10:]
            )
            if history_lines
            else "(start of conversation)"
        )

        prompt = JUDGE_TURN.format(
            history=history_str,
            response=turn["agent"],
            expected_stage=turn.get("expected_stage", "unknown"),
        )
        scores = llm_judge(prompt)
        turn_scores.append(
            {
                "user": turn["user"],
                "agent": turn["agent"],
                "scores": scores,
            }
        )

        history_lines.append({"role": "user", "content": turn["user"]})
        history_lines.append({"role": "assistant", "content": turn["agent"]})

    policy_violations = sum(
        1 for t in turn_scores if t["scores"].get("policy_compliant", 1) == 0
    )
    avg_helpful = (
        sum(t["scores"].get("helpful", 1) for t in turn_scores) / len(turn_scores)
        if turn_scores
        else 0
    )
    avg_correct = (
        sum(t["scores"].get("correct", 1) for t in turn_scores) / len(turn_scores)
        if turn_scores
        else 0
    )

    return {
        "policy_violations": policy_violations,
        "avg_helpfulness": avg_helpful,
        "avg_correctness": avg_correct,
        "turn_scores": turn_scores,
    }


def run_judge_on_all(runner_results: list[dict]) -> dict:
    all_scores = []
    for result in runner_results:
        scores = score_transcript(result["transcript"])
        all_scores.append({"scenario": result["name"], **scores})
        print(
            f"[JUDGE] {result['name']}: "
            f"policy_violations={scores['policy_violations']}, "
            f"helpfulness={scores['avg_helpfulness']:.2f}, "
            f"correctness={scores['avg_correctness']:.2f}"
        )

    total_violations = sum(s["policy_violations"] for s in all_scores)
    avg_helpful = (
        sum(s["avg_helpfulness"] for s in all_scores) / len(all_scores)
        if all_scores
        else 0
    )
    avg_correct = (
        sum(s["avg_correctness"] for s in all_scores) / len(all_scores)
        if all_scores
        else 0
    )

    return {
        "total_policy_violations": total_violations,
        "avg_helpfulness": avg_helpful,
        "avg_correctness": avg_correct,
        "scenario_scores": all_scores,
    }
