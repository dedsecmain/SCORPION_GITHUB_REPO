from scorpion.handoff import ChatGPTHandoff


def test_handoff_prompt_contains_task_bounded_history_and_image_note():
    handoff = ChatGPTHandoff(history_limit=2)
    history = [
        {"role": "user", "content": "old-1"},
        {"role": "assistant", "content": "old-2"},
        {"role": "user", "content": "recent-1"},
        {"role": "assistant", "content": "recent-2"},
    ]

    prompt = handoff.build_prompt("Analysiere den Screenshot", history=history, image_attached=True)

    assert "Analysiere den Screenshot" in prompt
    assert "recent-1" in prompt and "recent-2" in prompt
    assert "old-1" not in prompt and "old-2" not in prompt
    assert "manuell" in prompt.lower()
    assert "Scorpion" in prompt


def test_copy_and_open_opens_chatgpt_even_if_clipboard_fails():
    opened = []

    def broken_clipboard(_text):
        raise RuntimeError("clipboard busy")

    handoff = ChatGPTHandoff(
        clipboard_writer=broken_clipboard,
        browser_opener=lambda url: opened.append(url) or True,
    )
    result = handoff.copy_and_open("hello")

    assert result.copied is False
    assert result.opened is True
    assert result.prompt == "hello"
    assert "clipboard busy" in (result.error or "")
    assert opened == ["https://chatgpt.com/"]


def test_copy_and_open_reports_success():
    copied = []
    opened = []
    handoff = ChatGPTHandoff(
        clipboard_writer=lambda text: copied.append(text),
        browser_opener=lambda url: opened.append(url) or True,
    )

    result = handoff.copy_and_open("prompt")

    assert result.copied is True
    assert result.opened is True
    assert copied == ["prompt"]
