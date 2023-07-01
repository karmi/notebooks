import os
import argparse
import glob
import shutil

from datetime import datetime

from nbconvert import HTMLExporter
from nbconvert.writers.files import FilesWriter
from nbconvert.nbconvertapp import NbConvertApp

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from traitlets.config import get_config

import processors


def convert_single_notebook(app, notebook_path, output_dir):
    app.output_files_dir = os.path.join(
        output_dir, os.path.splitext(os.path.basename(notebook_path))[0]
    )
    app.writer.build_directory = app.output_files_dir
    app.convert_single_notebook(notebook_path)


def extract_metadata(html_file):
    with open(html_file, "r") as file:
        soup = BeautifulSoup(file, "html.parser")

    meta = soup.find_all("meta")
    # print(meta)

    data = {}
    for tag in meta:
        if "property" in tag.attrs:
            if tag.attrs["property"].lower() in [
                "og:title",
                "og:description",
                "og:article:published_time",
            ]:
                data[tag.attrs["property"].lower()] = tag.attrs["content"]

    return data


def create_homepage(metadata_list, template_file, output_dir):
    file_loader = FileSystemLoader(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "templates", "homepage"
        ),
    )
    env = Environment(loader=file_loader)

    print(metadata_list)

    template = env.get_template(template_file)

    output = template.render(pages=metadata_list)

    with open(os.path.join(output_dir, "index.html"), "w") as file:
        file.write(output)

    shutil.copytree(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "templates", "notebooks", "css"
        ),
        os.path.join(output_dir, "css"),
        dirs_exist_ok=True,
    )


def main(input_dir, output_dir):
    notebooks = glob.glob(os.path.join(input_dir, "*.ipynb"))

    config = get_config()

    config.TemplateExporter.template_name = "notebooks"
    config.TemplateExporter.extra_template_basedirs = ["./templates/"]

    config.Exporter.preprocessors = [
        processors.update_metadata.Preprocessor,
        processors.remove_cells.Preprocessor,
        processors.remove_output.Preprocessor,
        processors.remove_stderr.Preprocessor,
    ]

    app = NbConvertApp()
    app.config = config

    app.export_format = "html"
    app.exporter = HTMLExporter(app.config)
    app.writer = FilesWriter()

    app.output_base = "index"

    for notebook_path in notebooks:
        convert_single_notebook(app, notebook_path, output_dir)

    html_files = glob.glob(os.path.join(output_dir, "**/index.html"))

    metadata_list = []
    for html_file in html_files:
        print(f"Processing [{html_file}]")
        metadata = extract_metadata(html_file)
        metadata["dirname"] = os.path.split(os.path.dirname(html_file))[-1]
        metadata_list.append(metadata)

        metadata_list = sorted(
            metadata_list,
            key=lambda x: datetime.strptime(
                x.get("og:article:published_time", "1900-01-01"), "%Y-%m-%d"
            ),
            reverse=True,
        )

    create_homepage(
        metadata_list,
        "index.html.j2",
        output_dir,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_dir", help="Directory containing Jupyter notebooks", required=True
    )
    parser.add_argument(
        "--output_dir", help="Directory to write exported notebooks", required=True
    )
    args = parser.parse_args()

    main(args.input_dir, args.output_dir)
