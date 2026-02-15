"""Tests for the cleanup-results.sh script."""

import json
import os
import pathlib
import subprocess
import time

import pytest


# Resolve the script path relative to this test file
SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
CLEANUP_SCRIPT = SCRIPT_DIR / "cleanup-results.sh"


def _create_json_file(directory: pathlib.Path, name: str, age_days: int = 0) -> pathlib.Path:
    """Create a JSON file and set its modification time to `age_days` days ago."""
    filepath = directory / name
    filepath.write_text(json.dumps({"test": True, "name": name}))
    if age_days > 0:
        # Set mtime to age_days days ago
        old_time = time.time() - (age_days * 86400)
        os.utime(filepath, (old_time, old_time))
    return filepath


def _run_cleanup(results_dir: str, retention_days: int = 30, dry_run: bool = False) -> subprocess.CompletedProcess:
    """Run the cleanup script and return the completed process."""
    cmd = [
        "bash", str(CLEANUP_SCRIPT),
        "--results-dir", results_dir,
        "--retention-days", str(retention_days),
    ]
    if dry_run:
        cmd.append("--dry-run")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# 1. Dry-run mode does not delete files
# ---------------------------------------------------------------------------

class TestDryRunMode:
    def test_dry_run_does_not_delete_files(self, tmp_path):
        """Dry-run should report files that would be deleted but not remove them."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create files: 2 old (beyond retention), 1 recent
        old_file_1 = _create_json_file(results_dir, "old_result_1.json", age_days=45)
        old_file_2 = _create_json_file(results_dir, "old_result_2.json", age_days=60)
        recent_file = _create_json_file(results_dir, "recent_result.json", age_days=5)

        result = _run_cleanup(str(results_dir), retention_days=30, dry_run=True)

        assert result.returncode == 0
        # All files should still exist
        assert old_file_1.exists(), "Dry-run should not delete old_result_1.json"
        assert old_file_2.exists(), "Dry-run should not delete old_result_2.json"
        assert recent_file.exists(), "Dry-run should not delete recent_result.json"
        # Output should indicate dry-run
        assert "DRY RUN" in result.stdout
        assert "Would delete" in result.stdout or "would be deleted: 2" in result.stdout

    def test_dry_run_reports_correct_count(self, tmp_path):
        """Dry-run should report the correct number of files that would be deleted."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        _create_json_file(results_dir, "old_1.json", age_days=40)
        _create_json_file(results_dir, "old_2.json", age_days=50)
        _create_json_file(results_dir, "old_3.json", age_days=100)
        _create_json_file(results_dir, "new_1.json", age_days=1)

        result = _run_cleanup(str(results_dir), retention_days=30, dry_run=True)

        assert result.returncode == 0
        assert "would be deleted: 3" in result.stdout


# ---------------------------------------------------------------------------
# 2. Actual cleanup deletes old files
# ---------------------------------------------------------------------------

class TestActualCleanup:
    def test_cleanup_deletes_old_files(self, tmp_path):
        """Cleanup should delete JSON files older than retention days."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        old_file_1 = _create_json_file(results_dir, "old_plan.json", age_days=45)
        old_file_2 = _create_json_file(results_dir, "old_review.json", age_days=60)
        recent_file = _create_json_file(results_dir, "recent_impl.json", age_days=5)

        result = _run_cleanup(str(results_dir), retention_days=30, dry_run=False)

        assert result.returncode == 0
        # Old files should be deleted
        assert not old_file_1.exists(), "old_plan.json should have been deleted"
        assert not old_file_2.exists(), "old_review.json should have been deleted"
        # Recent file should remain
        assert recent_file.exists(), "recent_impl.json should not be deleted"
        assert "Files deleted: 2" in result.stdout

    def test_cleanup_only_deletes_json_files(self, tmp_path):
        """Cleanup should only delete .json files, not other file types."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        json_file = _create_json_file(results_dir, "old_result.json", age_days=45)
        xml_file = results_dir / "old_junit.xml"
        xml_file.write_text("<testsuites/>")
        old_time = time.time() - (45 * 86400)
        os.utime(xml_file, (old_time, old_time))

        lock_file = results_dir / "old_impl.lock"
        lock_file.write_text("")
        os.utime(lock_file, (old_time, old_time))

        result = _run_cleanup(str(results_dir), retention_days=30, dry_run=False)

        assert result.returncode == 0
        assert not json_file.exists(), "JSON file should be deleted"
        assert xml_file.exists(), "XML file should not be deleted"
        assert lock_file.exists(), "Lock file should not be deleted"

    def test_cleanup_does_not_delete_directories(self, tmp_path):
        """Cleanup should never delete directories, even if they match the pattern."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        subdir = results_dir / "subdir.json"
        subdir.mkdir()

        old_file = _create_json_file(results_dir, "old_result.json", age_days=45)

        result = _run_cleanup(str(results_dir), retention_days=30, dry_run=False)

        assert result.returncode == 0
        assert subdir.exists(), "Directory named subdir.json should not be deleted"
        assert not old_file.exists(), "JSON file should be deleted"

    def test_cleanup_no_old_files(self, tmp_path):
        """Cleanup should succeed with no deletions when no files are old enough."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        recent_1 = _create_json_file(results_dir, "recent_1.json", age_days=1)
        recent_2 = _create_json_file(results_dir, "recent_2.json", age_days=10)

        result = _run_cleanup(str(results_dir), retention_days=30, dry_run=False)

        assert result.returncode == 0
        assert recent_1.exists()
        assert recent_2.exists()
        assert "Files deleted: 0" in result.stdout


# ---------------------------------------------------------------------------
# 3. Retention threshold is respected
# ---------------------------------------------------------------------------

class TestRetentionThreshold:
    def test_custom_retention_days(self, tmp_path):
        """Files older than the custom retention period should be deleted."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # With 7-day retention: file at 10 days should be deleted, 3 days should not
        old_file = _create_json_file(results_dir, "week_old.json", age_days=10)
        recent_file = _create_json_file(results_dir, "three_days.json", age_days=3)

        result = _run_cleanup(str(results_dir), retention_days=7, dry_run=False)

        assert result.returncode == 0
        assert not old_file.exists(), "10-day-old file should be deleted with 7-day retention"
        assert recent_file.exists(), "3-day-old file should not be deleted with 7-day retention"

    def test_boundary_file_not_deleted(self, tmp_path):
        """A file exactly at the retention boundary should not be deleted.
        find -mtime +N matches files strictly older than N days."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # File at exactly 30 days should NOT be deleted (find -mtime +30 means > 30)
        boundary_file = _create_json_file(results_dir, "boundary.json", age_days=30)
        old_file = _create_json_file(results_dir, "old.json", age_days=31)

        result = _run_cleanup(str(results_dir), retention_days=30, dry_run=False)

        assert result.returncode == 0
        assert boundary_file.exists(), "File at exactly 30 days should not be deleted"
        assert not old_file.exists(), "File at 31 days should be deleted"

    def test_one_day_retention(self, tmp_path):
        """With 1-day retention, files older than 1 day should be deleted."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        old_file = _create_json_file(results_dir, "old.json", age_days=3)
        new_file = _create_json_file(results_dir, "new.json", age_days=0)

        result = _run_cleanup(str(results_dir), retention_days=1, dry_run=False)

        assert result.returncode == 0
        assert not old_file.exists(), "3-day-old file should be deleted with 1-day retention"
        assert new_file.exists(), "Brand new file should not be deleted"

    def test_large_retention_days(self, tmp_path):
        """With a very large retention period, no files should be deleted."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        file_1 = _create_json_file(results_dir, "file_1.json", age_days=100)
        file_2 = _create_json_file(results_dir, "file_2.json", age_days=200)

        result = _run_cleanup(str(results_dir), retention_days=365, dry_run=False)

        assert result.returncode == 0
        assert file_1.exists(), "100-day-old file should not be deleted with 365-day retention"
        assert file_2.exists(), "200-day-old file should not be deleted with 365-day retention"
        assert "Files deleted: 0" in result.stdout


# ---------------------------------------------------------------------------
# 4. Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_nonexistent_directory(self, tmp_path):
        """Script should fail with an error for a non-existent directory."""
        result = _run_cleanup(str(tmp_path / "nonexistent"), retention_days=30)
        assert result.returncode != 0
        assert "does not exist" in result.stderr

    def test_empty_directory(self, tmp_path):
        """Script should succeed with zero deletions on an empty directory."""
        results_dir = tmp_path / "empty_results"
        results_dir.mkdir()

        result = _run_cleanup(str(results_dir), retention_days=30, dry_run=False)

        assert result.returncode == 0
        assert "Files deleted: 0" in result.stdout

    def test_summary_shows_freed_space(self, tmp_path):
        """Summary output should report the freed space."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        _create_json_file(results_dir, "old.json", age_days=45)

        result = _run_cleanup(str(results_dir), retention_days=30, dry_run=False)

        assert result.returncode == 0
        assert "Space freed:" in result.stdout
