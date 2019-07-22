import setuptools
from pathlib import Path

README = Path(__file__).parent.absolute() / "readme.md"
README = README.read_text(encoding="utf8")

setuptools.setup(
    name="ogc-plugins-charm",
    version="0.0.1",
    author="Adam Stokes",
    author_email="adam.stokes@ubuntu.com",
    description="ogc-plugins-charm, a ogc plugin for working with juju charms",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/battlemidget/ogc-plugins-charm",
    packages=["ogc_plugins_charm"],
    entry_points={"ogc.plugins": "Charm = ogc_plugins_charm:Charm"},
    install_requires=[
        "ogc>=0.1.5,<1.0.0",
        "click>=7.0.0,<8.0.0",
        "sh>=1.12,<2.0",
        "pyyaml==3.13",
    ],
)
