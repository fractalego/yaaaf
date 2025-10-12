import re
from typing import Tuple


def strip_thought_tokens(answer: str) -> str:
    answer = re.sub(r"<think>(.*?)</think>", "", answer, flags=re.DOTALL | re.MULTILINE)
    return answer


def extract_thinking_content(answer: str) -> Tuple[str, str]:
    """
    Extract thinking content from the answer and return both the thinking content
    and the answer without thinking tags.

    Returns:
        Tuple of (thinking_content, answer_without_thinking)
    """
    pattern = r"<think>(.*?)</think>"
    match = re.search(pattern, answer, flags=re.DOTALL | re.MULTILINE)

    if match:
        thinking_content = match.group(1).strip()
        answer_without_thinking = re.sub(
            pattern, "", answer, flags=re.DOTALL | re.MULTILINE
        ).strip()
        return thinking_content, answer_without_thinking

    return "", answer


def get_first_text_between_tags(text: str, opening_tag: str, closing_tag: str) -> str:
    pattern = f"{opening_tag}(.*?){closing_tag}"
    match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    if match:
        return match.group(1).strip()

    pattern = f"{opening_tag}(.*)"
    match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    if match:
        return match.group(1).strip()

    return ""
