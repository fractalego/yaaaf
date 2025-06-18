import re


def strip_thought_tokens(answer: str) -> str:
    answer = re.sub(r"<think>(.*?)</think>", "", answer, flags=re.DOTALL | re.MULTILINE)
    return answer


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
