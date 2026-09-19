from scorpion.commands import CommandKind, parse_command


def test_parses_calculator_command():
    command = parse_command("öffne den rechner")
    assert command.kind is CommandKind.OPEN_APP
    assert command.target == "calculator"


def test_parses_browser_command():
    command = parse_command("mach den browser auf")
    assert command.kind is CommandKind.OPEN_APP
    assert command.target == "browser"


def test_non_command_stays_chat():
    command = parse_command("erklär mir quantenphysik")
    assert command.kind is CommandKind.CHAT


def test_parses_screen_inspection_command():
    command = parse_command("Scorpion, was ist auf meinem Bildschirm?")
    assert command.kind is CommandKind.SCREEN


def test_parses_focus_browser_command():
    command = parse_command("wechsel zum browser")
    assert command.kind is CommandKind.FOCUS_APP
    assert command.target == "browser"



def test_parses_build_mode_command():
    command = parse_command("Scorpion, Build Mode")
    assert command.kind is CommandKind.BUILD_MODE
    assert command.target == "build_mode"
