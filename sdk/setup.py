# SPDX-License-Identifier: Apache-2.0
from setuptools import setup, find_packages

setup(
    name="securecollab",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["requests", "tenseal"],
    entry_points={"console_scripts": ["securecollab=cli:main"]},
)
