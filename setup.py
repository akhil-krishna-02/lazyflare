from setuptools import setup, find_packages

setup(
    name="lazycloudflare",
    version="0.1.0",
    description="A fast, keyboard-driven Terminal User Interface (TUI) for Cloudflare.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Your Name",
    url="https://github.com/yourusername/lazycloudflare",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "textual>=0.8.0",
        "cloudflare>=3.0.0",
        "python-dotenv>=1.0.0"
    ],
    entry_points={
        "console_scripts": [
            "lazycloudflare=app:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    python_requires=">=3.8",
)
