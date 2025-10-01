#!/usr/bin/env python3
"""
Extract Service Account Credentials

Helper script to extract component values from a Google Cloud service account JSON file
and generate .env file entries.

Usage:
    python scripts/extract_service_account.py /path/to/service-account.json
    python scripts/extract_service_account.py /path/to/service-account.json --output .env
"""

import json
import sys
from pathlib import Path


def extract_credentials(json_path: str) -> dict:
    """Extract credential components from service account JSON."""
    with open(json_path, 'r') as f:
        data = json.load(f)

    required_fields = ['project_id', 'private_key_id', 'private_key', 'client_email', 'client_id']
    missing = [field for field in required_fields if field not in data]

    if missing:
        print(f"❌ Error: Missing required fields in JSON: {', '.join(missing)}")
        sys.exit(1)

    return {
        'GCP_PROJECT_ID': data['project_id'],
        'GCP_PRIVATE_KEY_ID': data['private_key_id'],
        'GCP_PRIVATE_KEY': data['private_key'],
        'GCP_CLIENT_EMAIL': data['client_email'],
        'GCP_CLIENT_ID': data['client_id']
    }


def format_env_output(credentials: dict) -> str:
    """Format credentials as .env file entries."""
    lines = [
        "# Google Cloud / BigQuery Credentials (extracted from service account JSON)",
        "",
    ]

    for key, value in credentials.items():
        # Escape the private key for .env format
        if key == 'GCP_PRIVATE_KEY':
            # Keep newlines as literal \n in the value
            value = value.replace('\n', '\\n')
            lines.append(f'{key}="{value}"')
        else:
            lines.append(f'{key}="{value}"')

    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/extract_service_account.py <service-account.json> [--output .env]")
        print("\nExtract credential components from Google Cloud service account JSON.")
        print("\nOptions:")
        print("  --output FILE    Write to file instead of stdout")
        sys.exit(1)

    json_path = sys.argv[1]

    if not Path(json_path).exists():
        print(f"❌ Error: File not found: {json_path}")
        sys.exit(1)

    print(f"📄 Reading service account JSON: {json_path}")

    try:
        credentials = extract_credentials(json_path)
        print(f"✅ Successfully extracted {len(credentials)} credential components")

        output = format_env_output(credentials)

        # Check if --output flag is present
        if '--output' in sys.argv:
            output_idx = sys.argv.index('--output')
            if output_idx + 1 < len(sys.argv):
                output_file = sys.argv[output_idx + 1]
                output_path = Path(output_file)

                # Check if file exists and ask for confirmation
                if output_path.exists():
                    response = input(f"⚠️  File {output_file} already exists. Append to it? (y/N): ")
                    if response.lower() != 'y':
                        print("Aborted.")
                        sys.exit(0)

                    # Append to existing file
                    with open(output_path, 'a') as f:
                        f.write('\n\n')
                        f.write(output)
                        f.write('\n')
                    print(f"✅ Appended credentials to: {output_file}")
                else:
                    # Write to new file
                    with open(output_path, 'w') as f:
                        f.write(output)
                        f.write('\n')
                    print(f"✅ Wrote credentials to: {output_file}")
            else:
                print("❌ Error: --output requires a filename")
                sys.exit(1)
        else:
            # Print to stdout
            print("\n" + "=" * 70)
            print("Copy the following lines to your .env file:")
            print("=" * 70)
            print(output)
            print("=" * 70)

        print("\n✅ Done! Your credentials are ready to use.")
        print("\nNext steps:")
        print("   1. Add these values to your .env file")
        print("   2. Add your AI provider API key (OPENAI_API_KEY, etc.)")
        print("   3. Run: python src/main.py --validate")

    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
