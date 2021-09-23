from setuptools import setup

setup(
    name='auto-extractor',
    version="0.0.4",
    description='Watch and auto extract zip files',
    author='wonderbeyond',
    install_requires=[
        'inotify',
        'chardet',
    ],
    packages=["auto_extractor"]
)
