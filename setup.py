# -*- coding: utf-8 -*-
import codecs
import os
import subprocess
import sys
from shutil import rmtree

from setuptools import setup, find_packages, Command

here = os.path.abspath(os.path.dirname(__file__))

__version__ = None
exec(open(f"{here}/slack_sdk/version.py").read())

long_description = ""
with codecs.open(os.path.join(here, "README.md"), encoding="utf-8") as readme:
    long_description = readme.read()

validate_dependencies = [
    "pytest>=6.2.5,<7",
    "pytest-asyncio<1",  # for async
    "Flask-Sockets>=0.2,<1",
    "Flask>=1,<2",  # TODO: Flask-Sockets is not yet compatible with Flask 2.x
    "Werkzeug<2",  # TODO: Flask-Sockets is not yet compatible with Flask 2.x
    "itsdangerous==1.1.0",  # TODO: Flask-Sockets is not yet compatible with Flask 2.x
    "Jinja2==3.0.3",  # https://github.com/pallets/flask/issues/4494
    "pytest-cov>=2,<3",
    "codecov>=2,<3",
    "flake8>=4,<5",
    "black==22.3.0",
    "click==8.0.4",  # black is affected by https://github.com/pallets/click/issues/2225
    "psutil>=5,<6",
    "databases>=0.5",
    # used only under slack_sdk/*_store
    "boto3<=2",
    # TODO: Upgrade to v2
    "moto>=3,<4",  # For AWS tests
]
codegen_dependencies = [
    "black==22.3.0",
]

needs_pytest = {"pytest", "test", "ptr"}.intersection(sys.argv)
pytest_runner = ["pytest-runner"] if needs_pytest else []


class BaseCommand(Command):
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print("\033[1m{0}\033[0m".format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def _run(self, s, command):
        try:
            self.status(s + "\n" + " ".join(command))
            subprocess.check_call(command)
        except subprocess.CalledProcessError as error:
            sys.exit(error.returncode)


class UploadCommand(BaseCommand):
    """Support setup.py upload. Thanks @kennethreitz!"""

    description = "Build and publish the package."

    def run(self):
        self._run(
            "Installing upload dependencies ...",
            [sys.executable, "-m", "pip", "install", "wheel"],
        )
        try:
            self.status("Removing previous builds ...")
            rmtree(os.path.join(here, "dist"))
            rmtree(os.path.join(here, "build"))
        except OSError:
            pass

        self._run(
            "Building Source and Wheel (universal) distribution ...",
            [sys.executable, "setup.py", "sdist", "bdist_wheel", "--universal"],
        )
        self._run(
            "Installing Twine dependency ...",
            [sys.executable, "-m", "pip", "install", "twine"],
        )
        self._run(
            "Uploading the package to PyPI via Twine ...",
            [sys.executable, "-m", "twine", "upload", "dist/*"],
        )


class CodegenCommand(BaseCommand):
    def run(self):
        self._run(
            "Installing required dependencies ...",
            [sys.executable, "-m", "pip", "install"] + codegen_dependencies,
        )

        header = (
            "# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "#\n"
            "#  *** DO NOT EDIT THIS FILE ***\n"
            "#\n"
            "#  1) Modify slack_sdk/web/client.py\n"
            "#  2) Run `python setup.py codegen`\n"
            "#\n"
            "# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "\n"
        )
        with open(f"{here}/slack_sdk/web/client.py", "r") as original:
            source = original.read()
            import re

            async_source = header + source
            async_source = re.sub("    def ", "    async def ", async_source)
            async_source = re.sub("from asyncio import Future\n", "", async_source)
            async_source = re.sub(
                "return self.api_call\(", "return await self.api_call(", async_source
            )
            async_source = re.sub(
                "-> SlackResponse", "-> AsyncSlackResponse", async_source
            )
            async_source = re.sub(
                "from .base_client import BaseClient, SlackResponse",
                "from .async_base_client import AsyncBaseClient, AsyncSlackResponse",
                async_source,
            )
            # from slack_sdk import WebClient
            async_source = re.sub(
                "class WebClient\(BaseClient\):",
                "class AsyncWebClient(AsyncBaseClient):",
                async_source,
            )
            async_source = re.sub(
                "from slack_sdk import WebClient",
                "from slack_sdk.web.async_client import AsyncWebClient",
                async_source,
            )
            async_source = re.sub("= WebClient\(", "= AsyncWebClient(", async_source)
            with open(f"{here}/slack_sdk/web/async_client.py", "w") as output:
                output.write(async_source)

            legacy_source = header + "from asyncio import Future\n" + source
            legacy_source = re.sub(
                "-> SlackResponse", "-> Union[Future, SlackResponse]", legacy_source
            )
            legacy_source = re.sub(
                "from .base_client import BaseClient, SlackResponse",
                "from .legacy_base_client import LegacyBaseClient, SlackResponse",
                legacy_source,
            )
            legacy_source = re.sub(
                "class WebClient\(BaseClient\):",
                "class LegacyWebClient(LegacyBaseClient):",
                legacy_source,
            )
            legacy_source = re.sub(
                "from slack_sdk import WebClient",
                "from slack_sdk.web.legacy_client import LegacyWebClient",
                legacy_source,
            )
            legacy_source = re.sub("= WebClient\(", "= LegacyWebClient(", legacy_source)
            with open(f"{here}/slack_sdk/web/legacy_client.py", "w") as output:
                output.write(legacy_source)

            self._run(
                "Running black (code formatter) ... ",
                [sys.executable, "-m", "black", f"{here}/slack_sdk"],
            )


class ValidateCommand(BaseCommand):
    """Support setup.py validate."""

    description = "Run Python static code analyzer (flake8), formatter (black) and unit tests (pytest)."

    user_options = [("test-target=", "i", "tests/{test-target}")]

    def initialize_options(self):
        self.test_target = ""

    def run(self):
        self._run(
            "Installing test dependencies ...",
            [sys.executable, "-m", "pip", "install"] + validate_dependencies,
        )
        self._run("Running black ...", [sys.executable, "-m", "black", f"{here}/slack"])
        self._run(
            "Running black ...", [sys.executable, "-m", "black", f"{here}/slack_sdk"]
        )
        self._run(
            "Running flake8 for legacy packages ...", [sys.executable, "-m", "flake8", f"{here}/slack"]
        )
        self._run(
            "Running flake8 for slack_sdk package ...", [sys.executable, "-m", "flake8", f"{here}/slack_sdk"]
        )

        target = self.test_target.replace("tests/", "", 1)
        self._run(
            "Running unit tests ...",
            [
                sys.executable,
                "-m",
                "pytest",
                "--cov-report=xml",
                f"--cov={here}/slack_sdk",
                f"tests/{target}",
            ],
        )


class UnitTestsCommand(BaseCommand):
    """Support setup.py validate."""

    description = "Run unit tests (pytest)."
    user_options = [("test-target=", "i", "tests/{test-target}")]

    def initialize_options(self):
        self.test_target = ""

    def run(self):
        target = self.test_target.replace("tests/", "", 1)
        self._run(
            "Running unit tests ...",
            [sys.executable, "-m", "pytest", f"tests/{target}",],
        )


class IntegrationTestsCommand(BaseCommand):
    """Support setup.py run_integration_tests"""

    description = "Run integration tests (pytest)."

    user_options = [
        ("test-target=", "i", "integration_tests/{test-target}"),
    ]

    def initialize_options(self):
        self.test_target = ""
        self.legacy = ""

    def run(self):
        target = self.test_target.replace("integration_tests/", "", 1)
        path = f"integration_tests/{target}"
        self._run(
            "Running integration tests ...", [sys.executable, "-m", "pytest", path,],
        )


setup(
    name="slack_sdk",
    version=__version__,
    description="The Slack API Platform SDK for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/slackapi/python-slack-sdk",
    author="Slack Technologies, LLC",
    author_email="opensource@slack.com",
    python_requires=">=3.6.0",
    include_package_data=True,
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Communications :: Chat",
        "Topic :: System :: Networking",
        "Topic :: Office/Business",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    keywords="slack slack-api web-api slack-rtm websocket chat chatbot chatops",
    packages=find_packages(
        exclude=[
            "docs",
            "docs-src",
            "docs-v2",
            "docs-src-v2",
            "docs-v3",
            "docs-src-v3",
            "integration_tests",
            "integration_tests_legacy",
            "tests",
            "tests.*",
            "tutorial",
        ]
    ),
    install_requires=[],
    extras_require={
        # pip install -e ".[testing]"
        "testing": validate_dependencies,
        # pip install -e ".[optional]"
        "optional": [
            # async modules depend on aiohttp
            "aiodns>1.0",
            # We recommend using 3.7.1+ for RTMClient
            # https://github.com/slackapi/python-slack-sdk/issues/912
            "aiohttp>=3.7.3,<4",
            # used only under slack_sdk/*_store
            "boto3<=2",
            # InstallationStore/OAuthStateStore
            "SQLAlchemy>=1,<2",
            # Socket Mode
            # websockets 9 is not compatible with Python 3.10
            "websockets>=10,<11" if sys.version_info.minor > 6 else "websockets>=9.1,<10",
            "websocket-client>=1,<2",
        ],
    },
    setup_requires=pytest_runner,
    test_suite="tests",
    tests_require=validate_dependencies,
    cmdclass={
        "upload": UploadCommand,
        "codegen": CodegenCommand,
        "validate": ValidateCommand,
        "unit_tests": UnitTestsCommand,
        "integration_tests": IntegrationTestsCommand,
    },
)
