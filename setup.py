from setuptools import setup, find_packages

setup(
    name="utils",
    version="0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "PyGithub==2.2.0",
        "python-dotenv==1.0.1",
        "requests>=2.23.0,<2.27.2",  # Compatible with redshift-connector
        "tqdm==4.66.2",
        "pyarrow>=2.0.0,<7.1.0",  # Compatible with awswrangler
        "boto3>=1.24.21,<1.25.0",  # Compatible with aiobotocore
        "charset-normalizer>=2.0,<3.0",  # Compatible with aiohttp
        "numpy>=1.21.0,<2.0.0",  # Compatible with awswrangler
        "pandas>=1.3.0,<2.0.0"  # Compatible with numpy 1.x
    ],
)