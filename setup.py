"""Setup script for Comment Tracker."""

from setuptools import setup, find_packages

setup(
    name="comment-tracker",
    version="1.0.0",
    description="Client comment history management, analytics, and L&L integration tool",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=[
        "Flask>=3.0",
        "click>=8.0",
        "pandas>=2.0",
        "openpyxl>=3.1",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "comment-tracker=run:main",
        ],
    },
)
