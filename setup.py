import setuptools
import ogc_plugins_charm as package
from pathlib import Path

README = Path(__file__).parent.absolute() / "readme.md"
README = README.read_text(encoding="utf8")

setuptools.setup(
    name=package.__plugin_name__,
    version=package.__version__,
    author=package.__author__,
    author_email=package.__author_email__,
    description=package.__description__,
    long_description=README,
    long_description_content_type="text/markdown",
    url=package.__git_repo__,
    py_modules=["ogc_plugins_charm"],
    entry_points={"ogc.plugins": "Charm = ogc_plugins_charm:Charm"},
    install_requires=[
        "ogc>=0.1.5,<1.0.0",
        "click>=7.0.0,<8.0.0",
        "sh>=1.12,<2.0",
        "pyyaml<6.0.0",
    ],
)
