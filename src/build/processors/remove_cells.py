from nbconvert.preprocessors import Preprocessor as Base


class Preprocessor(Base):
    def preprocess(self, nb, resources):
        TAGS = ["skip", "metadata"]

        new_cells = []
        for cell in nb.cells:
            if "tags" in cell.metadata and any(
                tag in cell.metadata["tags"] for tag in TAGS
            ):
                # print("Skipping cell", cell)
                continue
            new_cells.append(cell)
        nb.cells = new_cells
        return nb, resources
