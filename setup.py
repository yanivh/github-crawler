from setuptools import setup, find_packages

setup(
    name="utils",
    version="0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "PyGithub==2.2.0",
        "requests",
        "tqdm",
        "pyarrow"  # Compatible with awswrangler
    ],
)