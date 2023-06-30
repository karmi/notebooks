import os
import glob
import importlib

for m in sorted(
    [
        os.path.basename(m).replace(".py", "")
        for m in glob.glob(os.path.dirname(__file__) + "/*.py")
        if not os.path.basename(m).startswith("__")
    ]
):
    # print(f"Importing module [{m}]")
    importlib.import_module(f".{m}", __name__)
