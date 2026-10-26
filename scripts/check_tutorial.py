"""Exercise tutorial SQL only on a verified disposable GitHub CI database."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

# Support both direct script execution and import by the offline tests.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.tutorial_checks import FILES, TutorialChecks, require

ROOT = Path(__file__).resolve().parents[1]
PROJECT = re.compile(r'cu-ci-[0-9]+-[0-9]+\Z')
CLIENT = 'export MYSQL_PWD="$MARIADB_PASSWORD"; exec mariadb --abort-source-on-error --batch --raw --skip-column-names -ubenchmark engine_lab'


def validate_project(project):
    if not PROJECT.fullmatch(project):
        raise ValueError('Tutorial driver accepts only disposable cu-ci-<run>-<attempt> projects')

def command(argv, input_text=None):
    result = subprocess.run(argv, cwd=ROOT, input=input_text, text=True, encoding='utf-8',
                            errors='replace', capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Tutorial command failed')
    return result.stdout.strip()

def compose(project, *args, input_text=None):
    validate_project(project)
    return command(['docker', 'compose', '--env-file', str(ROOT/'.env'), '-f', str(ROOT/'compose.yaml'),
                    '-p', project, *args], input_text)

def identity(project):
    container = compose(project, 'ps', '-a', '-q', 'db')
    require(bool(container) and len(container.splitlines()) == 1, 'Expected one CI database')
    info = json.loads(command(['docker', 'inspect', container]))[0]
    labels = info['Config']['Labels']
    mounts = [m for m in info['Mounts'] if m['Destination'] == '/var/lib/mysql']
    require(labels.get('com.docker.compose.project') == project and
            labels.get('com.docker.compose.service') == 'db', 'Database labels do not match CI project')
    require(len(mounts) == 1 and mounts[0].get('Name') == project+'_db_data', 'Unexpected database volume')
    require(info['State']['Status'] == 'running' and not info['State'].get('OOMKilled'), 'Database is not running normally')
    return info['Id']

def sql(project, text):
    return compose(project, 'exec', '-T', 'db', 'sh', '-c', CLIENT, input_text=text+'\n')

def restart(project):
    identity(project)
    compose(project, 'restart', 'db')
    compose(project, 'up', '-d', '--wait', '--wait-timeout', '180', 'db')
    identity(project)


def run(project):
    validate_project(project)  # Before any Docker invocation, including inspection.
    identity(project)
    require(sql(project, "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND (LEFT(TABLE_NAME,4)='tut_' OR TABLE_NAME='ci_tutorial_sentinel');") == '0', 'Existing tutorial objects; refusing to overwrite')
    require(sql(project, "SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE() AND ROUTINE_NAME='tut_hammer';") == '0', 'Existing tutorial procedure; refusing to overwrite')
    version = sql(project, 'SELECT VERSION();')
    require('MariaDB' in version, 'MariaDB required')
    compose(project, 'exec', '-T', 'db', 'mkdir', '-p', '/tutorial')
    compose(project, 'cp', 'sql/tutorial/.', 'db:/tutorial/')
    sql(project, "CREATE TABLE ci_tutorial_sentinel (id INT PRIMARY KEY, note VARCHAR(32)); INSERT INTO ci_tutorial_sentinel VALUES (1,'preserve');")
    checks = TutorialChecks(lambda text: sql(project, text), lambda: restart(project))
    results = [checks.run_sequence(rocks) for rocks in (True, False)]
    sql(project, 'DROP TABLE ci_tutorial_sentinel;')
    evidence = dict(experiment='tutorial_sql_correctness', commit=os.environ.get('GITHUB_SHA','local'),
                    platform=platform.platform(), host_python=sys.version, server_version=version,
                    source_sha256={name:hashlib.sha256((ROOT/'sql/tutorial'/name).read_bytes()).hexdigest() for name in FILES},
                    sequences=results, scope='Linux amd64 CI correctness; four-engine SQL tested on amd64, not native ARM; no performance evidence')
    print('TUTORIAL_VALIDATION_JSON_BEGIN', flush=True)
    print(json.dumps(evidence, indent=2), flush=True)
    print('TUTORIAL_VALIDATION_JSON_END', flush=True)
    print('TUTORIAL SMOKE PASS', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    args = parser.parse_args()
    try:
        run(args.project)
    except Exception as error:
        print('TUTORIAL SMOKE FAILED:', str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
