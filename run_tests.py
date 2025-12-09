import pytest
import sys

if __name__ == "__main__":
    print("Running tests via script...")
    sys.exit(pytest.main(["tests", "-v"]))
