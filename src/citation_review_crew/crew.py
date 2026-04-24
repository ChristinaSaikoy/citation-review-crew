from crewai import Agent, Crew, LLM, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
import os


@CrewBase
class CitationReviewCrew:
    """CitationReviewCrew crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    def _llm(self) -> LLM:
        return LLM(
            model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE"),
            timeout=600,
        )

    @agent
    def review_coordinator(self) -> Agent:
        return Agent(
            config=self.agents_config["review_coordinator"],
            llm=self._llm(),
            verbose=True,
        )

    @agent
    def report_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["report_writer"],
            llm=self._llm(),
            verbose=True,
        )

    @task
    def evidence_comparison_task(self) -> Task:
        return Task(
            config=self.tasks_config["evidence_comparison_task"],
        )

    @task
    def review_report_task(self) -> Task:
        return Task(
            config=self.tasks_config["review_report_task"],
            output_file="report.md",
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
