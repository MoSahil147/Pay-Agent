# Interactive command line interface for manual testing.
# Each run starts a fresh Agent session; there is no persistence between runs.

from agent import Agent


def main():
    print("Pay-Agent: Payment Collection Assistant")
    print("Type 'quit' or 'exit' to end the session.\n")
    agent = Agent()
    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break
        if user_input.lower() in ("quit", "exit", "q"):
            print("Session ended. Goodbye!")
            break
        if not user_input:
            continue
        result = agent.next(user_input)
        print(f"Agent: {result['message']}\n")


if __name__ == "__main__":
    main()
