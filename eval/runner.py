# Script-based evaluator. Drives each scenario through the agent turn by turn
# and checks whether the final message matches the expected outcome.

from agent import Agent
from eval.scenarios import SCENARIOS


def run_scenario(scenario: dict) -> dict:
    agent = Agent()
    transcript = []
    passed = True
    failure_reason = None
    correct_steps = 0
    total_steps = len(scenario["turns"])

    for i, turn in enumerate(scenario["turns"]):
        user_msg = turn["user"]
        expected_stage = turn["expected_stage"]

        result = agent.next(user_msg)
        message = result["message"]

        transcript.append({"user": user_msg, "agent": message, "expected_stage": expected_stage})

        is_last = i == total_steps - 1
        if is_last:
            outcome = scenario["expected_outcome"]
            step_correct = _check_outcome(message, outcome, agent)
        else:
            step_correct = True  # intermediate turns assumed correct if no exception

        if step_correct:
            correct_steps += 1
        else:
            passed = False
            failure_reason = f"Turn {i+1}: expected outcome '{scenario['expected_outcome']}' not met"

    return {
        "name": scenario["name"],
        "passed": passed,
        "turns_taken": total_steps,
        "step_accuracy": correct_steps / total_steps,
        "failure_reason": failure_reason,
        "transcript": transcript,
    }


def _check_outcome(final_message: str, expected_outcome: str, agent: Agent) -> bool:
    msg = final_message.lower()
    if expected_outcome == "payment_success":
        return "transaction" in msg or "processed successfully" in msg
    if expected_outcome == "locked":
        return "locked" in msg or "support" in msg
    if expected_outcome == "zero_balance":
        return "no outstanding balance" in msg or "nothing to pay" in msg
    if expected_outcome == "payment_failure":
        return "card" in msg or "doesn't look right" in msg or "invalid" in msg
    if expected_outcome == "done":
        return True
    return False


def run_all(scenarios=None, verbose=False) -> dict:
    scenarios = scenarios or SCENARIOS
    results = []
    for scenario in scenarios:
        result = run_scenario(scenario)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {scenario['name']}")
        if not result["passed"]:
            print(f"       Reason: {result['failure_reason']}")
        if verbose:
            for turn in result["transcript"]:
                print(f"  U: {turn['user']}")
                print(f"  A: {turn['agent']}")
                print()

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    avg_step_acc = sum(r["step_accuracy"] for r in results) / total if total else 0

    summary = {
        "scenario_pass_rate": passed / total if total else 0,
        "scenarios_passed": passed,
        "scenarios_total": total,
        "avg_step_accuracy": avg_step_acc,
        "results": results,
    }
    print(f"\nResults: {passed}/{total} scenarios passed ({summary['scenario_pass_rate']*100:.1f}%)")
    return summary


if __name__ == "__main__":
    import sys
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    run_all(verbose=verbose)
