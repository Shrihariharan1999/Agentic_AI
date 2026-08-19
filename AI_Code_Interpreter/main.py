from agent import CodeInterpreterAgent


def main():

    agent = CodeInterpreterAgent()

    print("=" * 60)
    print("AI Code Interpreter")
    print("Type 'exit' to quit.")
    print("=" * 60)

    while True:

        user_query = input("\nYou: ").strip()

        if user_query.lower() == "exit":
            print("Goodbye!")
            break

        try:

            response = agent.run(user_query)

            print("\nAssistant:")
            print(response)

        except Exception as e:

            print("\nUnexpected Error:")
            print(e)


if __name__ == "__main__":
    main()