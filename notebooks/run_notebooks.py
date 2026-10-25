"""Execute every learning notebook in order and save local evidence copies."""

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/executed_notebooks"
OUTPUT.mkdir(parents=True, exist_ok=True)
for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
    print("Executing " + path.name, flush=True)
    notebook = nbformat.read(path, as_version=4)
    client = NotebookClient(
        notebook, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}
    )
    client.create_kernel_manager()
    client.km.kernel_spec.argv = [
        sys.executable,
        "-m",
        "ipykernel_launcher",
        "-f",
        "{connection_file}",
    ]
    client.execute()
    nbformat.write(notebook, OUTPUT / path.name)
    print("PASS " + path.name, flush=True)
