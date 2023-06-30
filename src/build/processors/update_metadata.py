import yaml
import logging

from nbconvert.preprocessors import Preprocessor as Base


class Preprocessor(Base):
    logger = logging.getLogger("NbConvertApp")

    def preprocess(self, nb, resources):
        TAG = "metadata"

        for cell in nb.cells:
            # If the cell has a 'metadata' tag
            if "tags" in cell.metadata and TAG in cell.metadata["tags"]:
                metadata = yaml.safe_load(self._transform_source(cell.source))
                self.logger.debug(f"Updating notebook with metadata: {metadata}")
                for key, value in metadata.items():
                    nb.metadata[key] = value

        return nb, resources

    def _transform_source(self, source):
        return "\n".join(line.lstrip("# ") for line in source.splitlines())
