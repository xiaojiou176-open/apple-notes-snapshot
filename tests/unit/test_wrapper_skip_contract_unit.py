import unittest
from pathlib import Path


class WrapperSkipContractUnitTests(unittest.TestCase):
    def test_skip_paths_mark_the_run_as_finalized_before_exit(self):
        repo_root = Path(__file__).resolve().parents[2]
        content = (repo_root / "scripts" / "core" / "notes_snapshot_wrapper.zsh").read_text(
            encoding="utf-8"
        )

        expected_sequences = [
            'log_line "flock busy, skip" >> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"\n    FINALIZED=1\n    exit 0',
            'log_line "notes snapshot already running (pid=$pid), skip" >> "$NOTES_SNAPSHOT_LOG_DIR/stdout.log"\n          FINALIZED=1\n          exit 0',
            'log_line "lock dir present (age=${LOCK_AGE_SEC}s < ttl=${NOTES_SNAPSHOT_LOCK_TTL_SEC}s), skip" >> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"\n          FINALIZED=1\n          exit 0',
            'log_line "failed to acquire lock after cleanup, skip" >> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"\n      FINALIZED=1\n      exit 1',
        ]

        for sequence in expected_sequences:
            self.assertIn(sequence, content)


if __name__ == "__main__":
    unittest.main()
