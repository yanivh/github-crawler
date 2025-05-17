from setuptools import setup, find_packages

setup(
    name="utils",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "PyGithub==2.2.0",
        "python-dotenv==1.0.1",
        "requests==2.31.0",
        "tqdm==4.66.2",
        "pyarrow",
        "boto3"
    ],
) 