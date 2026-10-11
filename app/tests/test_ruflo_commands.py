from scorpion.commands import CommandKind, parse_command


def test_ruflo_status_command():
    parsed = parse_command("Scorpion, Ruflo Status")
    assert parsed.kind is CommandKind.RUFLO_STATUS


def test_ruflo_plan_command_keeps_objective():
    text = "Ruflo plane ein Update für die Wakeword-Erkennung"
    parsed = parse_command(text)
    assert parsed.kind is CommandKind.RUFLO_PLAN
    assert parsed.target == text
