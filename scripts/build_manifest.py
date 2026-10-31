"""Collect allowlisted build records without starting a database or exposing secrets.

These are observations, not a package lock or a byte-identical rebuild guarantee.
Only OpenFlights preparation invokes this helper; measurements reuse its images.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess


IMAGE = re.compile(r'sha256:[0-9a-f]{64}\Z')
PINNED_BASE = re.compile(r'[a-z0-9][a-z0-9._:/-]*(?::[A-Za-z0-9_][A-Za-z0-9_.-]*)?@sha256:[0-9a-f]{64}\Z')
PACKAGE = re.compile(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9][a-z0-9-]*)?\Z')
VERSION = re.compile(r'[0-9][A-Za-z0-9.+:~_!-]*\Z')
ARCH = re.compile(r'[a-z0-9][a-z0-9-]*\Z')
INDEX_TYPES = {'application/vnd.oci.image.index.v1+json',
               'application/vnd.docker.distribution.manifest.list.v2+json'}
MANIFEST_TYPES = {'application/vnd.oci.image.manifest.v1+json',
                  'application/vnd.docker.distribution.manifest.v2+json'}
MAX_OUTPUT = 8 * 1024 * 1024


class RecordError(RuntimeError):
    """Intentionally excludes command output, environment and credential values."""


def require(condition, message):
    if not condition:
        raise RecordError(message)


def helper_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def command(argv, root, timeout=30):
    """Capture privately; even errors must never print resolved Compose or stderr."""
    try:
        result = subprocess.run(argv, cwd=root, check=False, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=timeout)
        require(result.returncode == 0, 'Build record command failed')
        require(len(result.stdout) <= MAX_OUTPUT, 'Build record output exceeds limit')
        return result.stdout.decode('utf-8')
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        raise RecordError('Build record command unavailable or timed out') from None


def json_output(value):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        raise RecordError('Invalid build metadata JSON') from None


def effective_inputs(root, config):
    """Resolved Compose stays in memory. Hash Dockerfiles; never retain build args."""
    require(isinstance(config, dict) and isinstance(config.get('services'), dict),
            'Invalid resolved build configuration')
    result = {}
    for role in ('db', 'runner'):
        build = config.get('services', {}).get(role, {}).get('build')
        require(isinstance(build, dict), 'Expected a local build definition for both images')
        context = build.get('context', str(root))
        require(isinstance(context, str) and '://' not in context and not context.startswith('git@'),
                'Build records require a local build context')
        context = (Path(root)/context).resolve()
        if 'dockerfile_inline' in build:
            text = build['dockerfile_inline']
            require(isinstance(text, str), 'Invalid inline Dockerfile')
            raw = text.encode('utf-8')
            location = 'inline'
        else:
            path = (context/build.get('dockerfile', 'Dockerfile')).resolve()
            try:
                raw = path.read_bytes()
            except OSError:
                raise RecordError('Effective Dockerfile unavailable') from None
            try:
                location = path.relative_to(root).as_posix()
            except ValueError:
                location = 'external Dockerfile (path omitted)'
            try:
                text = raw.decode('utf-8')
            except UnicodeError:
                raise RecordError('Effective Dockerfile is not UTF-8') from None
        require(len(raw) <= 1024 * 1024, 'Effective Dockerfile exceeds limit')
        bases = []
        for line in text.splitlines():
            if not re.match(r'^\s*FROM\s', line, re.I):
                continue
            words = line.split()
            if len(words) > 1 and words[1].startswith('--platform='):
                words.pop(1)
            reference = words[1] if len(words) > 1 else ''
            # Unresolved ARGs/stage aliases are not serialized as trusted base references.
            if PINNED_BASE.fullmatch(reference):
                bases.append(dict(reference=reference, declared_digest=reference.rsplit('@', 1)[1]))
            else:
                bases.append(dict(status='unavailable', reason='base_not_literal_digest_pin'))
        require(bool(bases), 'Effective Dockerfile has no FROM instruction')
        result[role] = dict(dockerfile=location, dockerfile_sha256=hashlib.sha256(raw).hexdigest(),
                            declared_bases=bases)
    return result


def image_metadata(info, expected):
    require(isinstance(info, dict) and info.get('Id') == expected and IMAGE.fullmatch(expected),
            'Build record image ID differs from immutable selection')
    require(info.get('Os') == 'linux' and info.get('Architecture') == 'amd64',
            'Build record image platform differs')
    rootfs = info.get('RootFS') or {}
    layers = rootfs.get('Layers')
    require(rootfs.get('Type') == 'layers' and isinstance(layers, list) and layers and
            all(isinstance(value, str) and IMAGE.fullmatch(value) for value in layers),
            'Missing or invalid image filesystem layer identities')
    volumes = (info.get('Config') or {}).get('Volumes') or {}
    require(isinstance(volumes, dict) and len(volumes) <= 16 and
            all(isinstance(path, str) and path.startswith('/') and path != '/' and
                not any(c in path for c in ',\r\n\x00') for path in volumes),
            'Unsupported image volume declaration for package probe')
    created = info.get('Created')
    require(isinstance(created, str) and re.fullmatch(r'[0-9T:.+Z-]{1,64}', created),
            'Invalid image creation timestamp')
    return dict(image_id=expected, docker_config_id=info['Id'],
                config_id_source='Docker image inspect Id; no registry output digest inferred',
                os='linux', architecture='amd64', created=created,
                rootfs_diff_ids=layers), sorted(volumes)


def package_inventory(text):
    packages = []
    seen = set()
    statuses = {'not-installed', 'config-files', 'half-installed', 'unpacked', 'half-configured',
                'triggers-awaited', 'triggers-pending', 'installed'}
    for line in text.splitlines():
        fields = line.split('\t')
        require(len(fields) == 4 and fields[3] in statuses, 'Malformed package inventory')
        name, version, architecture, status = fields
        if status != 'installed':
            continue
        require(PACKAGE.fullmatch(name) and VERSION.fullmatch(version) and ARCH.fullmatch(architecture),
                'Malformed installed package identity')
        key = (name, architecture)
        require(key not in seen, 'Duplicate installed package identity')
        seen.add(key)
        packages.append(dict(name=name, version=version, architecture=architecture))
    require(bool(packages), 'Empty installed package inventory')
    return sorted(packages, key=lambda p: (p['name'], p['architecture']))


def python_inventory(value):
    info = json_output(value)
    require(isinstance(info, dict) and isinstance(info.get('python_version'), str) and
            re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', info['python_version']), 'Malformed Python version')
    packages = info.get('distributions')
    require(isinstance(packages, list) and packages, 'Empty Python distribution inventory')
    selected = []
    seen = set()
    for package in packages:
        require(isinstance(package, dict), 'Malformed Python distribution')
        name, version = package.get('name'), package.get('version')
        require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name) and
                isinstance(version, str) and VERSION.fullmatch(version), 'Malformed Python distribution')
        normalized = re.sub(r'[-_.]+', '-', name).lower()
        require(normalized not in seen, 'Duplicate Python distribution')
        seen.add(normalized)
        selected.append(dict(name=name, version=version))
    return dict(python_version=info['python_version'], distributions=sorted(selected, key=lambda p: p['name'].lower()))


def probe_command(image, volumes, entrypoint, args):
    require(isinstance(image, str) and IMAGE.fullmatch(image), 'Package probe requires an immutable image ID')
    argv = ['docker', 'run', '--rm', '--pull=never', '--network=none', '--read-only',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--user=65534:65534',
            '--workdir=/', '--memory=128m', '--cpus=0.5', '--pids-limit=64',
            '--label=cu.build-record.probe=true']
    for path in volumes:
        argv += ['--mount', 'type=tmpfs,destination='+path+',tmpfs-size=1048576']
    return argv+['--entrypoint', entrypoint, image, *args]


def tool_versions(root, compose_version):
    versions = json_output(command(['docker', 'version', '--format', '{{json .}}'], root))
    require(isinstance(versions, dict), 'Invalid Docker version record')
    selected = dict(compose=compose_version)
    for side in ('Client', 'Server'):
        info = versions.get(side) or {}
        require(isinstance(info.get('Version'), str) and
                re.fullmatch(r'[0-9][A-Za-z0-9.+_-]*', info['Version']), 'Missing Docker version')
        selected[side.lower()] = {key: info[key] for key in ('Version', 'ApiVersion', 'GitCommit', 'GoVersion', 'Os', 'Arch')
                                  if isinstance(info.get(key), str) and len(info[key]) <= 128}
    try:
        output = command(['docker', 'buildx', 'version'], root, timeout=10)
        match = re.search(r'\bv[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+_-]*', output)
        require(match is not None, 'Buildx version unavailable')
        selected['buildx'] = dict(status='available', version=match[0])
    except RecordError:
        selected['buildx'] = dict(status='unavailable', reason='command_unavailable_or_invalid')
    selected['builder'] = builder_details(root) if selected['buildx']['status'] == 'available' else dict(
        status='unavailable', reason='buildx_unavailable')
    return selected


def parse_builder_details(text):
    """Select only root-level fields from Buildx's supported plain inspection.

    Names delimit nodes but are never returned. Indented labels/options are not
    fields, even when their text resembles Status or BuildKit version.
    """
    driver = None
    nodes_section = False
    nodes = []
    current = None
    names = set()
    for line in text.splitlines():
        match = re.fullmatch(r'([A-Za-z][A-Za-z ]*):[ \t]*(.*)', line)
        if match is None:
            continue
        key, value = match[1], match[2].strip()
        if key == 'Driver':
            require(driver is None and not nodes_section and value in
                    {'docker', 'docker-container', 'kubernetes', 'remote', 'cloud'},
                    'Ambiguous or unsupported selected builder driver')
            driver = value
        elif key == 'Nodes':
            require(not nodes_section and not value, 'Ambiguous selected builder nodes section')
            nodes_section = True
        elif key == 'Name' and nodes_section:
            require(bool(value) and value not in names, 'Ambiguous selected builder node boundary')
            names.add(value)
            current = {}
            nodes.append(current)
        elif key in {'Status', 'BuildKit version', 'Buildkit', 'BuildKit'}:
            require(nodes_section and current is not None, 'Ungrouped selected builder node field')
            field = 'status' if key == 'Status' else 'buildkit'
            require(field not in current, 'Duplicate selected builder node field')
            if field == 'status':
                require(value in {'running', 'inactive', 'stopped', 'error'}, 'Unknown selected builder node status')
            else:
                require(value in {'', 'N/A'} or
                        re.fullmatch(r'v?[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+_-]*', value),
                        'Invalid selected builder version')
                value = value if value not in {'', 'N/A'} else 'unavailable'
            current[field] = value
    require(driver is not None and nodes_section and bool(nodes), 'Selected builder details unavailable')
    for node in nodes:
        require('status' in node, 'Selected builder node status unavailable')
        node.setdefault('buildkit', 'unavailable')
        require(node['status'] != 'running' or node['buildkit'] != 'unavailable',
                'Running selected builder version unavailable')
    return dict(status='observed_without_bootstrap', driver=driver, nodes=nodes)


def builder_details(root):
    """Inspect existing state only; Buildx inspect does not support --format."""
    try:
        return parse_builder_details(command(['docker', 'buildx', 'inspect'], root, timeout=10))
    except RecordError:
        return dict(status='unavailable', reason='selected_builder_unavailable_or_unsupported')


def registry_manifest(reference, root):
    """Read only public manifest fields; never keep annotations or CLI error text."""
    try:
        value = json_output(command(['docker', 'buildx', 'imagetools', 'inspect', '--raw', reference], root, timeout=15))
        require(isinstance(value, dict) and value.get('schemaVersion') == 2, 'Unsupported registry manifest')
        digest = reference.rsplit('@', 1)[1]
        selection = 'direct manifest; platform not established by manifest alone'
        if value.get('mediaType') in INDEX_TYPES:
            matches = [item for item in value.get('manifests', [])
                       if item.get('platform', {}).get('os') == 'linux' and
                       item.get('platform', {}).get('architecture') == 'amd64' and
                       item.get('platform', {}).get('variant', '') in ('', 'v1')]
            require(len(matches) == 1 and IMAGE.fullmatch(matches[0].get('digest', '')),
                    'No unique registry platform manifest')
            digest = matches[0]['digest']
            child = reference.rsplit('@', 1)[0]+'@'+digest
            value = json_output(command(['docker', 'buildx', 'imagetools', 'inspect', '--raw', child], root, timeout=15))
            selection = 'linux/amd64 index descriptor'
        require(isinstance(value, dict) and value.get('schemaVersion') == 2 and
                value.get('mediaType') in MANIFEST_TYPES, 'Unsupported registry image manifest')
        config = value.get('config', {}).get('digest', '')
        layers = [item.get('digest', '') for item in value.get('layers', [])]
        require(IMAGE.fullmatch(config) and layers and all(IMAGE.fullmatch(d) for d in layers),
                'Invalid registry descriptor identities')
        return dict(status='resolved', platform_selection=selection, manifest_digest=digest,
                    config_digest=config, compressed_layer_digests=layers)
    except (RecordError, TypeError, AttributeError):
        return dict(status='unavailable', reason='registry_unavailable_or_no_unique_supported_manifest')


def capture_inputs(root, compose_config_argv):
    return effective_inputs(Path(root).resolve(), json_output(command(compose_config_argv, root)))


def collect(root, session, compose_config_argv, expected_inputs):
    root = Path(root).resolve()
    # This output includes resolved passwords. Keep it only in memory and select below.
    inputs = capture_inputs(root, compose_config_argv)
    require(inputs == expected_inputs, 'Effective Dockerfiles changed during preparation')
    tools = tool_versions(root, session['compose_version'])
    resolved = {}
    for info in inputs.values():
        for base in info['declared_bases']:
            if 'reference' in base:
                reference = base['reference']
                if reference not in resolved:
                    resolved[reference] = registry_manifest(reference, root) if tools['buildx']['status'] == 'available' else dict(
                        status='unavailable', reason='buildx_unavailable')
                base['registry'] = resolved[reference]
    images = {}
    for role in ('db', 'runner'):
        image = session['images'][role]
        # Full inspect remains private in memory. Serialize only image_metadata's allowlist.
        value = json_output(command(['docker', 'image', 'inspect', image], root))
        require(isinstance(value, list) and len(value) == 1, 'Expected one selected image record')
        info, volumes = image_metadata(value[0], image)
        argv = probe_command(image, volumes, '/usr/bin/dpkg-query',
                             ['-W', '-f=${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n'])
        info['installed_packages'] = package_inventory(command(argv, root))
        if role == 'runner':
            code = ("import importlib.metadata as m,json,platform;"
                    "print(json.dumps(dict(python_version=platform.python_version(),"
                    "distributions=[dict(name=d.metadata['Name'],version=d.version) for d in m.distributions()])))")
            info['python'] = python_inventory(command(probe_command(image, volumes, '/usr/local/bin/python', ['-c', code]), root))
        images[role] = info
    return dict(format_version=1, collector_sha256=helper_sha256(),
                source_commit=session['host']['commit'], source_sha256=session['source_sha256'],
                build_adapter_sha256=session.get('build_adapter_sha256'), inputs=inputs,
                tools=tools, images=images,
                limitations=['Installed versions are observations, not a signed package snapshot or dependency lock.',
                             'Declared bases and registry descriptors do not attest every build input.',
                             'Image IDs, registry manifests and filesystem diff IDs are distinct identifiers.'])


def verify(path, session):
    link = session.get('build_manifest')
    require(isinstance(link, dict) and link.get('file') == 'build-manifest.json', 'Missing build manifest link')
    target = Path(path).parent/'build-manifest.json'
    try:
        raw = target.read_bytes()
    except OSError:
        raise RecordError('Build manifest unavailable') from None
    require(hashlib.sha256(raw).hexdigest() == link.get('sha256'), 'Build manifest checksum differs')
    record = json_output(raw)
    require(isinstance(record, dict) and record.get('format_version') == 1 and
            isinstance(record.get('collector_sha256'), str) and
            re.fullmatch(r'[0-9a-f]{64}', record['collector_sha256']) and
            record.get('collector_sha256') == session['host'].get('build_manifest_helper_sha256') and
            record.get('source_commit') == session['host']['commit'] and
            record.get('source_sha256') == session['source_sha256'] and
            record.get('build_adapter_sha256') == session.get('build_adapter_sha256') and
            isinstance(record.get('images'), dict) and
            set(record.get('images', {})) == {'db', 'runner'} and
            all(record['images'][role].get('image_id') == image for role, image in session['images'].items()),
            'Build manifest identities differ from session')
