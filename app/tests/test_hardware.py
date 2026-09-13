from scorpion.hardware import HardwareProfile, classify_hardware


def test_balanced_profile_from_mocked_resources():
    profile = classify_hardware(total_ram_gb=24, available_ram_gb=16, vram_gb=8, logical_cores=16)
    assert profile.capability == "balanced"


def test_low_profile_when_memory_is_small():
    profile = classify_hardware(total_ram_gb=8, available_ram_gb=5, vram_gb=2, logical_cores=8)
    assert profile.capability == "low"


def test_performance_profile_requires_headroom():
    profile = classify_hardware(total_ram_gb=64, available_ram_gb=44, vram_gb=16, logical_cores=24)
    assert profile.capability == "performance"
