"""
ENI Batch Processor

Provides configurable batch retrieval and token estimation for ENI records.
"""

import logging
from typing import Any, Dict, Optional

import pandas as pd


logger = logging.getLogger(__name__)


class ENIBatchProcessor:
    """Handles configurable batch processing of ENI records."""

    def __init__(self, config_loader, bigquery_connector, log_manager):
        self.config = config_loader.get_eni_processing_config()
        self.bigquery_connector = bigquery_connector
        self.log_manager = log_manager

    def get_next_eni_batch(self, contact_id: str) -> pd.DataFrame:
        """Get the next batch of unprocessed ENI records for a contact.

        Falls back to JSON log manager if BigQuery processing log is not available.
        """
        try:
            processed_eni_ids = []
            try:
                processed_eni_ids = self.bigquery_connector.get_processed_eni_ids(contact_id)
            except Exception:
                # Fallback to local log manager
                processed_eni_ids = self.log_manager.get_processed_eni_ids(contact_id)

            limit = self.config.get('batch_size', 5)
            order_by = "logged_date DESC" if self.config.get('prioritize_recent_data', True) else None

            # Reuse existing filtered loader if available
            query = f"""
                SELECT eni_source_type, eni_source_subtype, contact_id, member_name,
                       description, logged_date, eni_id, affiliation_id, recurroo_id,
                       pd_deal_id, pd_note_id, at_deal_id, at_deal_activity_id,
                       at_request_id, at_request_activity_id, at_note_id
                FROM `{self.bigquery_connector.project_id}.{self.bigquery_connector.dataset_id}.{self.bigquery_connector.table_name}`
                WHERE contact_id = '{contact_id}'
                  AND description IS NOT NULL
                  AND TRIM(description) != ''
            """
            if processed_eni_ids:
                ids = "', '".join(processed_eni_ids)
                query += f" AND eni_id NOT IN ('{ids}')"
            if order_by:
                query += f" ORDER BY {order_by}"
            else:
                query += " ORDER BY logged_date DESC"
            if limit:
                query += f" LIMIT {int(limit)}"

            df = self.bigquery_connector.client.query(query).to_dataframe()
            return df
        except Exception as e:
            logger.error(f"Failed to get next ENI batch for {contact_id}: {e}")
            return pd.DataFrame()

    def estimate_batch_tokens(self, batch_data: pd.DataFrame) -> int:
        """Roughly estimate token count of batch by description lengths."""
        if batch_data is None or batch_data.empty:
            return 0
        description_lengths = batch_data['description'].fillna("").astype(str).str.len()
        # ~0.75 tokens per character heuristic
        estimated_tokens = float(description_lengths.sum()) * 0.75
        return int(estimated_tokens)

    def should_process_batch(self, batch_data: pd.DataFrame) -> bool:
        max_total = int(self.config.get('max_total_tokens_per_call', 15000) or 15000)
        return self.estimate_batch_tokens(batch_data) <= max_total


