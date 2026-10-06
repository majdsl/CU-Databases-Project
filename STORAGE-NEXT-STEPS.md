# Install and validate the storage experiment

These are six new project files. The archive does not replace existing benchmark
modules, Compose configuration, results, SQL, Dockerfiles or credentials. It has
not been committed or pushed to your GitHub repository.

1. Save `storage-experiment.zip` in the project root:
   `C:\Users\majdw\CU-Databases-Project`.
2. In that project's PowerShell terminal:

   ```powershell
   Expand-Archive .\storage-experiment.zip -DestinationPath . -Force
   python -m unittest discover -s tests -p test_storage.py -v
   ```

   On Windows, the Linux filesystem inventory test is skipped; it is included when
   tests run inside the Linux runner image. Send the test output before the pilot.

3. After tests are checked, start Docker Desktop in Linux-container mode. Keep the
   laptop plugged in with battery saver off if recording the power condition below.
   The command creates separate disposable databases and runs one trial per engine:

   ```powershell
   python scripts/run_storage.py --pilot --power-condition "plugged in; battery saver off"
   ```

   Existing `.env` credentials are used automatically. Do not upload `.env`.
   The pilot builds separate images and can take several minutes. It does not measure
   the existing database. Successful temporary volumes are removed; failed ones are
   retained for diagnosis. The normal database is not restarted by this script.

4. Send the final output and `Saved:` line, then upload the run's `results.json` and
   `summary.md`. A failure is not evidence of a completed storage experiment.

Do not launch the full five-round experiment until the pilot has been reviewed.
Do not commit the installation ZIP or `.env`. Commit the six extracted source/docs
files and, later, reviewed evidence as separate steps. We will guide those steps.

See `docs/storage-method.md` for interpretation. This package has unit-test validation;
real Docker/MariaDB execution still needs to be checked on your laptop.
