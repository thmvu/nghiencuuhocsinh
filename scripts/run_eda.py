from pathlib import Path
import nbformat
from nbclient import NotebookClient
root = Path(__file__).resolve().parents[1]
path = root / "notebooks/01_eda.ipynb"
nb = nbformat.read(path, as_version=4)
client = NotebookClient(nb, timeout=300, kernel_name="python3", resources={"metadata":{"path":str(root)}})
try:
    client.execute()
finally:
    nbformat.write(nb, path)
print("Executed:", path)
