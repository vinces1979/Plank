#!/usr/bin/env python
from setuptools import setup, find_packages

packages=find_packages()

setup(
    name = "plank",
    version = "0.1",
    description = "Simple irc ranking system",
    long_description = "permissive irc ranking bot with a simple redis store",
    author = "Vince Spicer",
    author_email = "vinces1979@gmail.com",
    url = "https://github.com/vinces1979/plank",
    license = "MIT",
    platforms = ["any"],
    packages=packages,
    keywords = [
        'ircbot', 'ranking'
    ],
    install_requires=[
        'twisted',
        'redis'
    ],
    classifiers = [
        'Development Status :: 4',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
