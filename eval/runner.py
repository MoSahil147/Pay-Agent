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
            step_correct = _check_outcome(message, scenario["expected_outcome"], agent)
        else:
            # Previously this was unconditionally True, meaning intermediate turns
            # were never evaluated and step_accuracy was always artificially high.
            # Now each turn is checked against its expected stage so the metric
            # reflects actual agent behaviour throughout the conversation.
            step_correct = _check_stage(message, expected_stage)

        if step_correct:
            correct_steps += 1
        else:
            passed = False
            if failure_reason is None:
                if is_last:
                    failure_reason = f"Turn {i+1}: expected outcome '{scenario['expected_outcome']}' not met"
                else:
                    failure_reason = f"Turn {i+1}: expected stage '{expected_stage}' not matched in agent response"

    return {
        "name": scenario["name"],
        "passed": passed,
        "turns_taken": total_steps,
        "step_accuracy": correct_steps / total_steps,
        "failure_reason": failure_reason,
        "transcript": transcript,
    }


def _check_stage(message: str, expected_stage: str) -> bool:
    """Loose keyword check for intermediate turns. Returns True when the agent
    response is consistent with the expected conversation stage."""
    msg = message.lower()
    if expected_stage == "lookup":
        return "account" in msg
    if expected_stage == "verify":
        return "name" in msg
    if expected_stage == "verify_secondary":
        return any(k in msg for k in ("date of birth", "aadhaar", "pincode", "verification"))
    if expected_stage == "balance":
        return "balance" in msg or "outstanding" in msg
    if expected_stage == "collect_payment":
        return any(k in msg for k in ("card", "amount", "cvv", "expiry", "name on", "pay"))
    if expected_stage == "done":
        return "transaction" in msg or "processed successfully" in msg
    if expected_stage == "locked":
        return "locked" in msg or "support" in msg
    return True


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
