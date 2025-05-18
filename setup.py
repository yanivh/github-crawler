from setuptools import setup, find_packages

setup(
    name="utils",
    version="0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "PyGithub==2.2.0",
        "requests==2.31.0",
        "tqdm==4.66.2",
        "pyarrow"  # Compatible with awswrangler
    ],
)
