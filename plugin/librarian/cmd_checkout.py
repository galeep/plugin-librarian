"""Checkout command implementation."""

import json
import sys
from pathlib import Path

from .checkout import find_skill_path, checkout_skill


def cmd_checkout(args):
    """Checkout a skill or agent to a local directory."""
    skill_spec = args.skill
    destination = Path(args.dir) if args.dir else Path.cwd()

    print(f"Searching for: {skill_spec}")

    # Find the skill
    skill_path = find_skill_path(skill_spec)
    if not skill_path:
        print(f"Error: Skill/agent not found: {skill_spec}")
        print(f"\nTip: Use 'librarian find <name>' to search for skills/agents")
        sys.exit(1)

    print(f"Found: {skill_path}")
    print(f"Destination: {destination}")
    print()

    # Perform checkout
    result = checkout_skill(skill_path, destination, preserve_structure=not args.flat)

    if result.success:
        print(f"Success: {result.message}")
        print(f"\nFiles copied:")
        for f in result.files_copied:
            print(f"  {f}")

        if result.metadata.get("_checkout"):
            checkout_info = result.metadata["_checkout"]
            print(f"\nCheckout info:")
            print(f"  Source: {checkout_info['source']}")
            print(f"  Timestamp: {checkout_info['timestamp']}")

        if result.metadata and "_checkout" not in str(result.metadata):
            print(f"\nMetadata extracted:")
            for key, value in result.metadata.items():
                if key != "_checkout":
                    if isinstance(value, (list, dict)):
                        print(f"  {key}: {json.dumps(value, indent=4)}")
                    else:
                        print(f"  {key}: {value}")

        print(f"\nMetadata saved to: {result.target_path / '.librarian-checkout.json'}")
    else:
        print(f"Error: {result.message}")
        sys.exit(1)
