#!/usr/bin/env python3
import subprocess

import tomli


def read_pyproject_deps():
    """Read dependencies from pyproject.toml."""
    with open("pyproject.toml", "rb") as f:
        pyproject = tomli.load(f)

    deps = pyproject["project"]["dependencies"]
    return deps


def get_installed_versions(packages):
    """Get installed versions of packages."""
    versions = {}
    for pkg in packages:
        try:
            result = subprocess.run(["pip", "show", pkg], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if line.startswith("Version: "):
                        versions[pkg] = line.split(": ")[1].strip()
                        break
        except Exception as e:
            print(f"Error getting version for {pkg}: {e}")
    return versions


def update_requirements(deps_with_versions):
    """Update requirements.txt with versioned dependencies."""
    requirements = []
    for pkg, version in deps_with_versions.items():
        if version:
            requirements.append(f"{pkg}=={version}")
        else:
            requirements.append(pkg)

    with open("requirements.txt", "w") as f:
        f.write("\n".join(sorted(requirements)) + "\n")


def main():
    """Main function to sync dependencies."""
    print("Reading dependencies from pyproject.toml...")
    deps = read_pyproject_deps()

    print("Getting installed versions...")
    versions = get_installed_versions(deps)

    print("Updating requirements.txt...")
    update_requirements(versions)

    print("Done! Dependencies synced.")
    print("\nInstalled versions:")
    for pkg, version in sorted(versions.items()):
        print(f"  {pkg}=={version}")


if __name__ == "__main__":
    main()
