"""AI 에이전트 기본 클래스"""
from abc import ABC, abstractmethod
from typing import Optional
import time


class BaseAgent(ABC):
    """모든 AI 에이전트의 기본 클래스"""

    def __init__(self, agent_id: str, name: str, role: str):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.last_execution_time: float = 0.0
        self.execution_count: int = 0

    @abstractmethod
    def execute(self, input_data: dict) -> dict:
        """에이전트 실행. 하위 클래스에서 구현."""
        pass

    def run(self, input_data: dict) -> dict:
        """에이전트 실행 래퍼 (타이밍 및 로깅)"""
        start = time.time()
        try:
            result = self.execute(input_data)
            self.last_execution_time = time.time() - start
            self.execution_count += 1
            return {
                "agent_id": self.agent_id,
                "agent_name": self.name,
                "status": "success",
                "execution_time": round(self.last_execution_time, 3),
                "result": result,
            }
        except Exception as e:
            self.last_execution_time = time.time() - start
            return {
                "agent_id": self.agent_id,
                "agent_name": self.name,
                "status": "error",
                "execution_time": round(self.last_execution_time, 3),
                "error": str(e),
                "result": {},
            }

    def get_status(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "executions": self.execution_count,
            "last_time": round(self.last_execution_time, 3),
        }
