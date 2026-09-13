from scorpion.memory import ConversationMemory


def test_memory_persists_and_limits_turns(tmp_path):
    path = tmp_path / "memory.json"
    memory = ConversationMemory(path, max_messages=3)
    for i in range(5):
        memory.append("user", f"m{i}")
    reloaded = ConversationMemory(path, max_messages=3)
    assert [x["content"] for x in reloaded.messages()] == ["m2", "m3", "m4"]
