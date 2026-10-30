"""Build and verify the project from Windows or Linux without running benchmarks."""
import argparse
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def output_access_guidance():
    """Explain host access without assuming mode bits describe Docker UID mapping."""
    if sys.platform != "linux":
        return ("For results-directory permissions and Docker Desktop file sharing, see docs/setup.md. "
                "Setup does not change ownership or permissions or delete existing data.")
    directory = shlex.quote(str(ROOT / "results"))
    lines = ["The runner uses UID/GID 10001 and must be able to create files in the results directory.",
             "On an ordinary rootful Docker host, grant this directory access if it is not already configured:"]
    if shutil.which("setfacl") is None:
        lines += ["setfacl is not on PATH. On Ubuntu/Debian, install the acl package first:",
                  "  sudo apt-get update", "  sudo apt-get install acl"]
    lines += [f"  mkdir -p -- {directory}",
              f"  setfacl -m u:10001:rwx -- {directory}",
              "The container write probe is authoritative; existing ACLs may already grant access.",
              "Rootless/user-remapped Docker and SELinux can need different host configuration; see docs/setup.md.",
              "Setup does not change ownership or permissions or delete existing data."]
    return "\n".join(lines)


def command(label, argv, capture=False):
    print(f"\n== {label} ==", flush=True)
    try:
        return subprocess.run(argv, cwd=ROOT, check=True, text=True,
                              stdout=subprocess.PIPE if capture else None)
    except FileNotFoundError as exc:
        raise RuntimeError(f"{label}: executable not found. Install Docker with Compose and put it on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"{label} failed (exit {exc.returncode}). Stop here and inspect the output above.") from exc


def setup(project=None):
    if project is not None and not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
        raise ValueError("Project name must start with a lowercase letter or digit and use a-z, 0-9, _ or -.")
    compose = ["docker", "compose"] + (["-p", project] if project else [])
    platform = command("Check Docker engine", ["docker", "info", "--format",
                       "{{.OSType}}/{{.Architecture}}"], capture=True).stdout.strip()
    if platform not in ("linux/x86_64", "linux/amd64"):
        raise RuntimeError(f"Docker reports {platform!r}; this five-engine build requires a Linux amd64 engine. "
                           "Other architectures are not validated; see docs/setup.md.")
    command("Check Compose", compose + ["version"])
    if sys.platform == "linux":
        print("\n== Native Linux output prerequisite ==", flush=True)
        print(output_access_guidance(), flush=True)
    command("Preserve or create local credentials", [sys.executable, "scripts/init_env.py"])
    command("Fetch and verify route data", [sys.executable, "scripts/fetch_openflights.py"])
    (ROOT / "results").mkdir(exist_ok=True)
    command("Build Python runner", compose + ["build", "runner"])
    try:
        command("Check benchmark output permissions", compose + ["run", "--rm", "--no-deps",
            "runner", "python", "-c", "import tempfile; "
            "d=tempfile.TemporaryDirectory(prefix='.setup-probe-', dir='/results'); "
            "d.cleanup(); print('PASS: runner can write /results')"])
    except RuntimeError as exc:
        raise RuntimeError(str(exc) + "\n" + output_access_guidance()) from exc
    command("Run unit tests", compose + ["run", "--rm", "--no-deps", "runner", "python",
            "-m", "unittest", "discover", "-s", "tests", "-v"])
    command("Build five-engine MariaDB", compose + ["build", "db"])
    command("Start database and wait for health", compose + ["up", "-d", "--wait",
            "--wait-timeout", "180", "db"])
    command("Verify all five actual engines and row contents", compose + ["run", "--rm", "runner"])
    print("\nSETUP PASS: output is writable, unit tests passed, and all five engines passed.", flush=True)
    print("No benchmark was run. Continue with the README pilot; preserve your .env and database volume.")
    if project:
        print(f"For this stack, include -p {project} in subsequent docker compose commands.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-name", help="Optional isolated Compose project name (used by CI).")
    args = parser.parse_args()
    try:
        setup(args.project_name)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"SETUP FAILED: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Setup interrupted; existing credentials and database volumes are retained.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
