from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent_tool import (rag_summarize, analyze_budget_tool, analyze_placement_tool, analyze_keyword_tool, analyze_search_tool, analyze_search_term_tool, fill_context_for_report)
from Agent.middleware import monitor_tool, log_before_model, report_prompt_switch



class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[rag_summarize, analyze_budget_tool,analyze_placement_tool,analyze_keyword_tool,analyze_search_tool,analyze_search_term_tool, fill_context_for_report],
            middleware=[monitor_tool, log_before_model, report_prompt_switch]
        )


    def execute_stream(self, message: list):
        input_dict = {
            "messages": message
        }
        # 第三个参数context就是上下文runtime中的信息，就是我们做提示词切换的标记
        for chunk in self.agent.stream(input_dict, stream_mode="values", context={"report": False}):
            latest_message = chunk["messages"][-1]
            if latest_message.content:
                yield latest_message.content.strip() + "\n"
