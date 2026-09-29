"""Read-only runner cgroup-v2 CPU counters; missing counters are not zero."""
from pathlib import Path
import time

COUNTERS = ('usage_usec', 'user_usec', 'system_usec', 'nr_periods',
            'nr_throttled', 'throttled_usec')


def parse_stat(text):
    values = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in COUNTERS:
            value = int(parts[1])
            if value < 0 or parts[0] in values:
                raise ValueError('Invalid CPU counter')
            values[parts[0]] = value
    if 'usage_usec' not in values:
        raise ValueError('Missing CPU usage counter')
    return values


def quota_cpus(text):
    quota, period = text.split()
    period = int(period)
    if period <= 0:
        raise ValueError('Invalid CPU period')
    if quota == 'max':
        return None
    quota = int(quota)
    if quota <= 0:
        raise ValueError('Invalid CPU quota')
    return quota / period


def snapshot(root=Path('/sys/fs/cgroup')):
    result = {'wall_ns': time.perf_counter_ns(), 'process_cpu_ns': time.process_time_ns()}
    try:
        result['cpu_stat'] = parse_stat((root / 'cpu.stat').read_text())
        result['cpu_max'] = (root / 'cpu.max').read_text().strip()
        result['quota_cpus'] = quota_cpus(result['cpu_max'])
    except (OSError, ValueError) as error:
        result['unavailable_reason'] = type(error).__name__
    return result


def difference(before, after):
    wall = (after['wall_ns'] - before['wall_ns']) / 1e9
    process = (after['process_cpu_ns'] - before['process_cpu_ns']) / 1e9
    if wall <= 0 or process < 0:
        raise ValueError('Invalid CPU measurement interval')
    result = {'window': 'worker setup, writes and teardown; excludes load and data verification',
              'window_seconds': wall, 'process_cpu_seconds': process,
              'process_average_cores': process / wall, 'before': before, 'after': after}
    if 'unavailable_reason' in before or 'unavailable_reason' in after:
        result['cgroup_status'] = 'unavailable'
        return result
    if before['cpu_max'] != after['cpu_max']:
        result['cgroup_status'] = 'quota_changed'
        return result
    common = before['cpu_stat'].keys() & after['cpu_stat'].keys()
    delta = {k: after['cpu_stat'][k] - before['cpu_stat'][k] for k in common}
    if any(v < 0 for v in delta.values()):
        result['cgroup_status'] = 'counter_reset'
        return result
    result.update(cgroup_status='available', counter_delta=delta,
                  cgroup_average_cores=delta['usage_usec'] / 1e6 / wall)
    return result
