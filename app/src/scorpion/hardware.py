from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class HardwareProfile:
    capability: str
    total_ram_gb: float
    available_ram_gb: float
    vram_gb: float | None
    cpu_logical: int
    cpu_physical: int | None = None
    gpu_name: str | None = None


def classify_hardware(*, total_ram_gb: float, available_ram_gb: float, vram_gb: float | None, logical_cores: int, cpu_physical: int | None = None, gpu_name: str | None = None) -> HardwareProfile:
    vram = vram_gb or 0.0
    if total_ram_gb >= 48 and available_ram_gb >= 24 and vram >= 12 and logical_cores >= 16:
        capability = "performance"
    elif total_ram_gb >= 16 and available_ram_gb >= 10 and vram >= 6 and logical_cores >= 8:
        capability = "balanced"
    else:
        capability = "low"
    return HardwareProfile(
        capability=capability,
        total_ram_gb=round(float(total_ram_gb), 2),
        available_ram_gb=round(float(available_ram_gb), 2),
        vram_gb=None if vram_gb is None else round(float(vram_gb), 2),
        cpu_logical=int(logical_cores),
        cpu_physical=cpu_physical,
        gpu_name=gpu_name,
    )


class HardwareProfiler:
    def __init__(self, *, runner=None):
        self._runner = runner or subprocess.run

    def _nvidia_info(self) -> tuple[float | None, str | None]:
        try:
            result = self._runner(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if getattr(result, "returncode", 1) != 0:
                return None, None
            line = (getattr(result, "stdout", "") or "").splitlines()[0]
            name, memory_mb = [part.strip() for part in line.rsplit(",", 1)]
            return float(memory_mb) / 1024.0, name
        except Exception:
            return None, None

    def profile(self) -> HardwareProfile:
        try:
            import psutil
        except ImportError as exc:
            raise RuntimeError("psutil fehlt. Führe setup_scorpion.bat erneut aus.") from exc

        mem = psutil.virtual_memory()
        vram_gb, gpu_name = self._nvidia_info()
        return classify_hardware(
            total_ram_gb=mem.total / (1024 ** 3),
            available_ram_gb=mem.available / (1024 ** 3),
            vram_gb=vram_gb,
            logical_cores=psutil.cpu_count(logical=True) or 1,
            cpu_physical=psutil.cpu_count(logical=False),
            gpu_name=gpu_name,
        )
