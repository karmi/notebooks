from nbconvert.preprocessors import Preprocessor as Base
from nbformat.notebooknode import NotebookNode


class Preprocessor(Base):
    def preprocess_cell(self, cell: NotebookNode, resources: dict, index: int):
        if cell.cell_type == "code":
            cell.outputs = [
                output
                for output in cell.outputs
                if output.output_type != "stream" or output.name != "stderr"
            ]
        return cell, resources
