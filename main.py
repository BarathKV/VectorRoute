from agent.agent import Agent

from agent.clasical_agent import ClassicalAgent

if __name__ == "__main__":
    # agent = ClassicalAgent()
    # user_input = "What is the current weather in New York?"
    # result, tools_used = agent.run(user_input)
    # print("Final Result:", result)
    # print("Tools Used:", tools_used)

    agent = Agent()
    user_input = "What is the current weather in New York?"
    result, tools_used = agent.run(user_input)
    print("Final Result:", result)
    print("Tools Used:", tools_used)