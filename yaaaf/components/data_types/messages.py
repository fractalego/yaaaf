from typing import List, Callable
from pydantic import BaseModel, Field

from yaaaf.components.agents.settings import task_completed_tag, task_paused_tag


class Utterance(BaseModel):
    role: str = Field(
        ...,
        description="The role of the utterance, e.g., 'user', 'assistant', 'system'",
    )
    content: str = Field(..., description="The content of the utterance")


class PromptTemplate(BaseModel):
    prompt: str = Field(..., description="The prompt template string")

    def complete(self, **kwargs) -> str:
        return (
            self.prompt.replace("{task_completed_tag}", task_completed_tag)
            .replace("{task_paused_tag}", task_paused_tag)
            .format(**kwargs)
        )


class Messages(BaseModel):
    utterances: List[Utterance] = Field(
        default_factory=list, description="List of utterances in the conversation"
    )

    def add_system_prompt(self, prompt: str | PromptTemplate) -> "Messages":
        if isinstance(prompt, PromptTemplate):
            try:
                prompt = prompt.complete()
            except KeyError as e:
                # If the template has placeholders but no parameters were provided,
                # use the raw prompt string as a fallback
                prompt = prompt.prompt
        system_prompt = Utterance(role="system", content=prompt)
        return Messages(utterances=[system_prompt] + self.utterances)

    def set_system_prompt(self, prompt: str | PromptTemplate) -> "Messages":
        """Replace or set the system prompt, removing any existing system messages."""
        if isinstance(prompt, PromptTemplate):
            try:
                prompt = prompt.complete()
            except KeyError as e:
                # If the template has placeholders but no parameters were provided,
                # use the raw prompt string as a fallback
                prompt = prompt.prompt
        system_prompt = Utterance(role="system", content=prompt)
        # Filter out any existing system prompts
        non_system_utterances = [u for u in self.utterances if u.role != "system"]
        return Messages(utterances=[system_prompt] + non_system_utterances)

    def add_assistant_utterance(self, content: str) -> "Messages":
        assistant_utterance = Utterance(role="assistant", content=content)
        return Messages(utterances=self.utterances + [assistant_utterance])

    def add_user_utterance(self, content: str) -> "Messages":
        user_utterance = Utterance(role="user", content=content)
        return Messages(utterances=self.utterances + [user_utterance])

    def apply(self, f: Callable) -> "Messages":
        """
        Apply a function to each utterance in the messages.

        Args:
            f: A function that takes an Utterance and returns a modified Utterance.

        Returns:
            A new Messages object with the modified utterances.
        """
        for utterance in self.utterances:
            utterance.content = f(utterance.content)
        return self

    def __repr__(self):
        return "\n".join(
            [f"{utterance.role}: {utterance.content}" for utterance in self.utterances]
        )

    def __str__(self):
        return self.__repr__()
