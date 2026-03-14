"""
Utility script to get the machine ID for license generation
Run this script on the client machine to get the machine ID
"""

import sys
import os

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "shared"))

from license_manager import MachineIdentifier


def main():
    print("=" * 50)
    print("Machine ID Generator")
    print("=" * 50)
    print()

    machine_id = MachineIdentifier.get_machine_id()

    print(f"Your Machine ID: {machine_id}")
    print()
    print("Copy this Machine ID and use it to generate a license")
    print("on the server's admin dashboard.")
    print()
    print("=" * 50)

    # Copy to clipboard if possible
    try:
        import pyperclip

        pyperclip.copy(machine_id)
        print("Machine ID copied to clipboard!")
    except ImportError:
        print("Install pyperclip to auto-copy to clipboard: pip install pyperclip")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
