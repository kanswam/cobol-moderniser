from setuptools import setup, find_packages

setup(
    name="cobol-moderniser",
    version="0.1.0",
    description="Autonomous migration of legacy COBOL to modern Python using AI agent swarms",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Kannan Swamy",
    url="https://github.com/kanswam/cobol-moderniser",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "anthropic>=0.20.0",
    ],
    entry_points={
        "console_scripts": [
            "cobol-moderniser=cobol_moderniser.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Office/Business :: Financial",
    ],
)
