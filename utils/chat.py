import argparse

from agent.agent import Agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llama3.2:3b", help="Ollama model to use")
    # parser.add_argument("--model", default="functiongemma:latest", help="Ollama model to use")
    args = parser.parse_args()

    agent = Agent(model=args.model)

    print(f"Chat ready with model {args.model}. Press Ctrl-D to exit.")

    try:
        while True:
            try:
                user_input = input("You: ")
            except EOFError:
                print("\nGoodbye.")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # response, tools_used = agent.run(user_input)
            response, tools_used = agent.ask(user_input)
            print(f"\n\nTools used: {tools_used}")

            response_dict = dict(response)

            content = response_dict.get("content", "")

            print(f"Agent: {content}\n\n")


    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")


if __name__ == "__main__":
    main()
