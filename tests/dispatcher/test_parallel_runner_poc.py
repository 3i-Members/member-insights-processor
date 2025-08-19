import time
import pytest


class _StubConfigLoader:
	def __init__(self, enable=True, workers=3, batch_size=10):
		self._cfg = {
			'enable': enable,
			'max_concurrent_contacts': workers,
			' selection': {
				'sql_file': None,
				'batch_size': batch_size,
			},
			'claims': {
				'enabled': True,
				'ttl_seconds': 5,
				'backoff_seconds': {'min': 1, 'max': 2},
			},
		}

	def get_parallel_config(self):
		# Note: ensure exact keys expected by main.py
		return {
			'enable': self._cfg['enable'],
			'max_concurrent_contacts': self._cfg['max_concurrent_contacts'],
			'selection': {'sql_file': None, 'batch_size': 10},
			'claims': self._cfg['claims'],
		}


class _StubBQ:
	def __init__(self, ids):
		self._ids = list(ids)

	def connect(self):
		return True

	def get_contact_ids_from_sql(self, sql_text, variables=None, offset=None, limit=None):
		o = int(offset or 0)
		l = int(limit or len(self._ids))
		return self._ids[o:o + l]

	def get_unique_contact_ids(self, limit=None):
		return self._ids[: int(limit) if limit else None]


@pytest.mark.timeout(10)
def test_parallel_dispatcher_poc(monkeypatch):
	# Lazy import to avoid heavy module import during collection
	from src.main import MemberInsightsProcessor

	# Patch initializer to avoid real setup
	def _fake_init(self):
		self.config_loader = _StubConfigLoader(enable=True, workers=4, batch_size=5)
		self.bigquery_connector = _StubBQ([f"CNT-TEST{i:03d}" for i in range(20)])
		# Attributes accessed but not needed in this test
		self.log_manager = None
		self.enhanced_logger = None

	monkeypatch.setattr(MemberInsightsProcessor, "_initialize_components", _fake_init, raising=True)

	# Track concurrency
	active = {"count": 0, "max": 0}
	processed = []

	def fake_process_contact(self, contact_id: str, system_prompt_key: str = "structured_insight", dry_run: bool = False):
		active["count"] += 1
		active["max"] = max(active["max"], active["count"])
		# Simulate small work
		time.sleep(0.03)
		processed.append(contact_id)
		active["count"] -= 1
		return {
			"contact_id": contact_id,
			"success": True,
			"processed_eni_ids": [],
			"skipped_eni_ids": [],
			"errors": [],
			"files_created": [],
			"airtable_records": [],
		}

	monkeypatch.setattr(MemberInsightsProcessor, "process_contact", fake_process_contact, raising=True)

	p = MemberInsightsProcessor("config/config.yaml", None)
	# Use explicit IDs to make the cap deterministic for this POC
	explicit_ids = [f"CNT-TEST{i:03d}" for i in range(17)]
	summary = p.process_multiple_contacts(
		contact_ids=explicit_ids,
		system_prompt_key="structured_insight",
		dry_run=True,
		max_contacts=17,
		contact_ids_sql=None,
		selection_batch_size=7,
		job_start_time="2025-01-01T00:00:00Z",
	)

	# Assertions
	assert summary["successful_contacts"] == 17
	assert summary["failed_contacts"] == 0
	assert len(summary["contact_results"]) == 17
	# Verify concurrency did not exceed configured workers (4)
	assert active["max"] <= 4
	# No duplicates
	assert len(set(processed)) == 17
