from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from tep_studio.simulation.validation.artifacts import utc_now


@dataclass(frozen=True)
class ReferenceSource:
    name: str
    url: str
    description: str
    filename: str
    required: bool = False


REFERENCE_SOURCES = {
    "ricker_archive": ReferenceSource(
        name="ricker_archive",
        url="https://github.com/camaramm/tennessee-eastman-challenge",
        description="Mirror of Ricker Tennessee Eastman Challenge archive materials.",
        filename="ricker_archive.html",
    ),
    "mv_per_dataset": ReferenceSource(
        name="mv_per_dataset",
        url="https://github.com/mv-per/tennessee-eastman-dataset",
        description="Public Tennessee Eastman dataset with normal and fault Excel files.",
        filename="mv_per_dataset.html",
    ),
    "adchem_2015_pdf": ReferenceSource(
        name="adchem_2015_pdf",
        url="https://skoge.folk.ntnu.no/prost/proceedings/adchem2015/media/papers/0010.pdf",
        description="Bathelt, Ricker, and Jelali ADCHEM 2015 revised TEP paper.",
        filename="ADCHEM15_0010.pdf",
    ),
    "mv_per_mode1_normal_50": ReferenceSource(
        name="mv_per_mode1_normal_50",
        url="https://raw.githubusercontent.com/mv-per/tennessee-eastman-dataset/main/data/mode1_normal_50.xlsx",
        description="Representative public Mode 1 normal dataset candidate.",
        filename="mode1_normal_50.xlsx",
    ),
}


def download_reference(source: ReferenceSource, cache_dir: Path, *, timeout: float = 30.0) -> dict[str, str | bool]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / source.filename
    payload = {
        "name": source.name,
        "url": source.url,
        "description": source.description,
        "path": str(target),
        "downloaded": False,
        "timestamp_utc": utc_now(),
        "sha256": "",
        "error": "",
    }
    try:
        with urlopen(source.url, timeout=timeout) as response:
            data = response.read()
        target.write_bytes(data)
        payload["downloaded"] = True
        payload["sha256"] = hashlib.sha256(data).hexdigest()
    except (OSError, URLError, TimeoutError) as exc:
        if source.required:
            raise RuntimeError(f"Could not download required reference {source.name}: {exc}") from exc
        payload["error"] = str(exc)
    return payload


def download_references(names: list[str], cache_dir: Path) -> list[dict[str, str | bool]]:
    manifests = []
    for name in names:
        source = REFERENCE_SOURCES[name]
        manifests.append(download_reference(source, cache_dir))
    return manifests

