from traitlets.config import get_config

import processors

c = get_config()

c.TemplateExporter.template_name = "notebooks"
c.TemplateExporter.extra_template_basedirs = ["./templates/"]

c.Exporter.preprocessors = [
    processors.update_metadata.Preprocessor,
    processors.remove_cells.Preprocessor,
    processors.remove_output.Preprocessor,
    processors.remove_stderr.Preprocessor,
]
