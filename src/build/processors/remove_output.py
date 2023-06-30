from nbconvert.preprocessors import Preprocessor as Base
from nbformat.notebooknode import NotebookNode


class Preprocessor(Base):
    def preprocess_cell(self, cell: NotebookNode, resources: dict, index: int):
        TAG = "hide-output"

        if "tags" in cell.metadata and TAG in cell.metadata["tags"]:
            cell.outputs = []

        return cell, resources
