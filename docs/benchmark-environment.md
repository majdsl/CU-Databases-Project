# Team laptop environment record

Observed on **October 9, 2026 (Europe/Berlin)** from PowerShell output supplied by the team.
This is a later environment snapshot, not a contemporaneous record of the September or October 6 benchmarks.
Preserve the metadata inside each archived run as the source for its recorded runtime conditions.

## Host and Docker environment

| Item | Observed value | Interpretation |
| --- | --- | --- |
| CPU | AMD Ryzen 5 7530U with Radeon Graphics | Windows CPU name |
| Physical cores | 6 | Reported by Win32_Processor |
| Logical processors | 12 | Reported by Win32_Processor |
| Windows-visible physical memory | 15.4 GiB, rounded to one decimal | TotalPhysicalMemory divided by PowerShell's 1GB (2^30 bytes); not a DIMM capacity inventory |
| Operating system | Microsoft Windows 11 Home | Win32_OperatingSystem.Caption |
| Windows version / build | 10.0.26200 / 26200 | Reported Windows version and build |
| Docker-visible CPUs | 12 | Daemon-visible count, not each container's CPU quota |
| Docker-visible memory | 8,000,094,208 bytes (about 7.45 GiB) | Daemon-visible memory at observation time; not measured workload consumption |
| Docker Engine server | 29.8.0 | ServerVersion; not the Docker Desktop application version |
| Docker kernel | 6.18.40.1-microsoft-standard-WSL2 | Linux engine on WSL2 |
| Docker Compose | v5.5.1 | CLI-reported version |

Docker Desktop's Linux engine was initially stopped. The first command printed zero CPUs/memory
and blank version/kernel fields alongside a connection error. **Those values are invalid and excluded.**
The values above were captured after the team started Docker Desktop and the command succeeded.

## Commands and captured values

Run these separately from PowerShell when collecting a new snapshot. They do not change the database.

```powershell
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors
Get-CimInstance Win32_ComputerSystem | Select-Object @{Name="RAM_GB";Expression={[math]::Round($_.TotalPhysicalMemory / 1GB, 1)}}
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber
docker info --format 'CPUs={{.NCPU}} MemoryBytes={{.MemTotal}} ServerVersion={{.ServerVersion}} Kernel={{.KernelVersion}}'
docker compose version
```

Successful Docker output:

```text
CPUs=12 MemoryBytes=8000094208 ServerVersion=29.8.0 Kernel=6.18.40.1-microsoft-standard-WSL2
Docker Compose version v5.5.1
```

## Relationship to the experiments

- Container CPU and memory limits are separate from host and Docker-visible resources.
  Check each experiment's Compose file and saved runtime/cgroup metadata.
- Power conditions are recorded per run; this hardware snapshot does not establish the power
  mode, background load or thermal conditions during any earlier measurement.
- The [recovery findings](recovery-findings.md) and [storage findings](storage-findings.md)
  link to original evidence. Do not replace historical server versions, image identities,
  source hashes or settings with this snapshot.
- The Docker Desktop application version, storage-device/filesystem details, explicit WSL
  configuration and complete historical host conditions have not yet been captured here.
  The runner base is now [digest-pinned](runner-image.md); rebuild validation and
  clean-checkout reproduction remain separate tasks.
