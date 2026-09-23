"""Execute the Gate A notebook and retain its outputs for audit."""
from pathlib import Path

import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parents[1]
path = root / "notebooks/02_preprocessing.ipynb"
notebook = nbformat.read(path, as_version=4)
client = NotebookClient(
    notebook, timeout=300, kernel_name="python3",
    resources={"metadata": {"path": str(root)}},
)
try:
    client.execute()
finally:
    nbformat.write(notebook, path)
print("Executed:", path)
