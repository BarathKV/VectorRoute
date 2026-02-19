from abc import ABC, abstractmethod

class BaseAgent(ABC):
    def __init__(self, tool_selector, vectordb):
        self.tool_selector = tool_selector
        self.vectordb = vectordb

    @abstractmethod
    def run(self, query: str):
        pass
