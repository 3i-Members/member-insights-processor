"""
Enhanced logging system for Member Insights Processor.
Provides comprehensive logging with real-time monitoring, file rotation, and detailed tracking.
"""

import os
import sys
import logging
import logging.handlers
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import threading
import time
from pathlib import Path

class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m'   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)

class ProcessingMetricsLogger:
    """Tracks and logs processing metrics in real-time"""
    
    def __init__(self):
        self.start_time = None
        self.metrics = {
            'contacts_processed': 0,
            'eni_groups_processed': 0,
            'ai_calls_made': 0,
            'ai_calls_successful': 0,
            'ai_calls_failed': 0,
            'files_created': 0,
            'airtable_records_created': 0,
            'errors_encountered': 0,
            'records_processed': 0,
            'records_filtered': 0
        }
        self.contact_timings = {}
        self.eni_group_timings = {}
        self.lock = threading.Lock()
        
    def start_processing(self):
        """Mark the start of processing"""
        self.start_time = datetime.now()
        
    def log_contact_start(self, contact_id: str):
        """Log start of contact processing"""
        with self.lock:
            self.contact_timings[contact_id] = {'start': datetime.now()}
            
    def log_contact_end(self, contact_id: str, success: bool):
        """Log end of contact processing"""
        with self.lock:
            if contact_id in self.contact_timings:
                self.contact_timings[contact_id]['end'] = datetime.now()
                self.contact_timings[contact_id]['success'] = success
                self.contact_timings[contact_id]['duration'] = (
                    self.contact_timings[contact_id]['end'] - 
                    self.contact_timings[contact_id]['start']
                ).total_seconds()
            
            if success:
                self.metrics['contacts_processed'] += 1
                
    def log_eni_group_processing(self, contact_id: str, eni_type: str, eni_subtype: str, 
                                records_count: int, success: bool, duration: float = 0):
        """Log ENI group processing"""
        with self.lock:
            self.metrics['eni_groups_processed'] += 1
            self.metrics['records_processed'] += records_count
            
            group_key = f"{contact_id}_{eni_type}_{eni_subtype}"
            self.eni_group_timings[group_key] = {
                'contact_id': contact_id,
                'eni_type': eni_type,
                'eni_subtype': eni_subtype,
                'records_count': records_count,
                'success': success,
                'duration': duration,
                'timestamp': datetime.now()
            }
            
    def log_ai_call(self, success: bool, model: str, duration: float = 0):
        """Log AI API call"""
        with self.lock:
            self.metrics['ai_calls_made'] += 1
            if success:
                self.metrics['ai_calls_successful'] += 1
            else:
                self.metrics['ai_calls_failed'] += 1
                
    def log_file_created(self):
        """Log file creation"""
        with self.lock:
            self.metrics['files_created'] += 1
            
    def log_airtable_record(self):
        """Log Airtable record creation"""
        with self.lock:
            self.metrics['airtable_records_created'] += 1
            
    def log_error(self):
        """Log error occurrence"""
        with self.lock:
            self.metrics['errors_encountered'] += 1
            
    def log_filtering(self, total_records: int, filtered_records: int):
        """Log record filtering"""
        with self.lock:
            self.metrics['records_filtered'] += (total_records - filtered_records)
            
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current processing metrics"""
        with self.lock:
            total_duration = 0
            if self.start_time:
                total_duration = (datetime.now() - self.start_time).total_seconds()
                
            ai_success_rate = 0
            if self.metrics['ai_calls_made'] > 0:
                ai_success_rate = (self.metrics['ai_calls_successful'] / self.metrics['ai_calls_made']) * 100
                
            return {
                **self.metrics,
                'total_duration_seconds': total_duration,
                'ai_success_rate_percent': ai_success_rate,
                'avg_records_per_contact': (
                    self.metrics['records_processed'] / max(1, self.metrics['contacts_processed'])
                ),
                'current_time': datetime.now().isoformat()
            }

class EnhancedLogger:
    """Enhanced logging system with real-time monitoring and comprehensive tracking"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.log_dir = Path(config.get('log_dir', 'logs'))
        self.log_dir.mkdir(exist_ok=True)
        
        # Create processing metrics tracker
        self.metrics = ProcessingMetricsLogger()
        
        # Initialize loggers
        self._setup_loggers()
        
        # Real-time monitoring thread
        self.monitoring_active = False
        self.monitoring_thread = None
        
    def _setup_loggers(self):
        """Set up comprehensive logging configuration"""
        
        # Main application logger
        self.logger = logging.getLogger('member_insights')
        self.logger.setLevel(getattr(logging, self.config.get('level', 'INFO')))
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Main log file handler with rotation
        main_log_file = self.log_dir / 'member_insights.log'
        main_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        main_handler.setLevel(logging.DEBUG)
        main_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        main_handler.setFormatter(main_formatter)
        self.logger.addHandler(main_handler)
        
        # Error-only log file
        error_log_file = self.log_dir / 'errors.log'
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(main_formatter)
        self.logger.addHandler(error_handler)
        
        # Performance/metrics log file
        metrics_log_file = self.log_dir / 'metrics.log'
        self.metrics_handler = logging.handlers.RotatingFileHandler(
            metrics_log_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        self.metrics_logger = logging.getLogger('metrics')
        self.metrics_logger.setLevel(logging.INFO)
        self.metrics_logger.addHandler(self.metrics_handler)
        
        # AI processing log file
        ai_log_file = self.log_dir / 'ai_processing.log'
        ai_handler = logging.handlers.RotatingFileHandler(
            ai_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=3
        )
        self.ai_logger = logging.getLogger('ai_processing')
        self.ai_logger.setLevel(logging.DEBUG)
        ai_handler.setFormatter(main_formatter)
        self.ai_logger.addHandler(ai_handler)
        
        # Data processing log file
        data_log_file = self.log_dir / 'data_processing.log'
        data_handler = logging.handlers.RotatingFileHandler(
            data_log_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        self.data_logger = logging.getLogger('data_processing')
        self.data_logger.setLevel(logging.DEBUG)
        data_handler.setFormatter(main_formatter)
        self.data_logger.addHandler(data_handler)
        
    def start_monitoring(self, interval: int = 30):
        """Start real-time metrics monitoring"""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, args=(interval,))
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        self.logger.info(f"Started real-time monitoring (interval: {interval}s)")
        
    def stop_monitoring(self):
        """Stop real-time metrics monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1)
        self.logger.info("Stopped real-time monitoring")
        
    def _monitoring_loop(self, interval: int):
        """Real-time monitoring loop"""
        while self.monitoring_active:
            try:
                metrics = self.metrics.get_current_metrics()
                self.log_metrics_snapshot(metrics)
                
                # Print real-time summary to console
                if metrics['contacts_processed'] > 0 or metrics['eni_groups_processed'] > 0:
                    summary = (
                        f"📊 PROCESSING STATUS: "
                        f"Contacts: {metrics['contacts_processed']}, "
                        f"ENI Groups: {metrics['eni_groups_processed']}, "
                        f"AI Calls: {metrics['ai_calls_made']} "
                        f"({metrics['ai_success_rate_percent']:.1f}% success), "
                        f"Errors: {metrics['errors_encountered']}, "
                        f"Duration: {metrics['total_duration_seconds']:.1f}s"
                    )
                    self.logger.info(summary)
                    
                time.sleep(interval)
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(1)
                
    def log_metrics_snapshot(self, metrics: Dict[str, Any]):
        """Log current metrics snapshot"""
        metrics_json = json.dumps(metrics, indent=2)
        self.metrics_logger.info(f"METRICS_SNAPSHOT: {metrics_json}")
        
    def log_contact_processing_start(self, contact_id: str, total_records: int, filtered_records: int):
        """Log the start of contact processing"""
        self.metrics.log_contact_start(contact_id)
        self.metrics.log_filtering(total_records, filtered_records)
        
        self.logger.info(f"🚀 STARTING CONTACT PROCESSING: {contact_id}")
        self.logger.info(f"   📊 Total records: {total_records}")
        self.logger.info(f"   ✅ Filtered records: {filtered_records} ({(filtered_records/total_records*100):.1f}%)")
        self.data_logger.info(f"Contact {contact_id}: {total_records} -> {filtered_records} records after filtering")
        
    def log_contact_processing_end(self, contact_id: str, result: Dict[str, Any]):
        """Log the end of contact processing"""
        success = result.get('success', False)
        self.metrics.log_contact_end(contact_id, success)
        
        status = "✅ SUCCESS" if success else "❌ FAILED"
        self.logger.info(f"🏁 CONTACT PROCESSING {status}: {contact_id}")
        self.logger.info(f"   📝 Processed ENI IDs: {len(result.get('processed_eni_ids', []))}")
        self.logger.info(f"   📁 Files created: {len(result.get('files_created', []))}")
        self.logger.info(f"   🗄️  Airtable records: {len(result.get('airtable_records', []))}")
        self.logger.info(f"   ⚠️  Errors: {len(result.get('errors', []))}")
        
        # Log detailed errors if any
        for error in result.get('errors', []):
            self.logger.error(f"   ERROR: {error}")
            self.metrics.log_error()
            
    def log_eni_group_start(self, contact_id: str, eni_type: str, eni_subtype: str, record_count: int):
        """Log start of ENI group processing"""
        self.logger.info(f"📂 Processing {eni_type}/{eni_subtype} for {contact_id} ({record_count} records)")
        self.data_logger.info(f"ENI Group Start: {contact_id} - {eni_type}/{eni_subtype} - {record_count} records")
        
    def log_eni_group_end(self, contact_id: str, eni_type: str, eni_subtype: str, 
                         record_count: int, success: bool, duration: float):
        """Log end of ENI group processing"""
        self.metrics.log_eni_group_processing(contact_id, eni_type, eni_subtype, record_count, success, duration)
        
        status = "✅" if success else "❌"
        self.logger.info(f"{status} Completed {eni_type}/{eni_subtype} in {duration:.2f}s")
        self.data_logger.info(f"ENI Group End: {contact_id} - {eni_type}/{eni_subtype} - Success: {success} - Duration: {duration:.2f}s")
        
    def log_ai_call_start(self, model: str, eni_type: str, eni_subtype: str, record_count: int):
        """Log start of AI processing call"""
        self.logger.info(f"🤖 Calling {model} for {eni_type}/{eni_subtype} ({record_count} records)")
        self.ai_logger.info(f"AI Call Start: {model} - {eni_type}/{eni_subtype} - {record_count} records")
        
    def log_ai_call_end(self, model: str, eni_type: str, eni_subtype: str, 
                       success: bool, duration: float, response_length: int = 0):
        """Log end of AI processing call"""
        self.metrics.log_ai_call(success, model, duration)
        
        status = "✅" if success else "❌"
        self.logger.info(f"{status} {model} completed in {duration:.2f}s (response: {response_length} chars)")
        self.ai_logger.info(f"AI Call End: {model} - Success: {success} - Duration: {duration:.2f}s - Response length: {response_length}")
        
    def log_context_loading(self, eni_type: str, eni_subtype: str, context_files: List[str]):
        """Log context file loading"""
        files_str = " + ".join(context_files) if len(context_files) > 1 else context_files[0] if context_files else "none"
        self.logger.debug(f"📖 Context loaded for {eni_type}/{eni_subtype}: {files_str}")
        self.data_logger.debug(f"Context loading: {eni_type}/{eni_subtype} - Files: {files_str}")
        
    def log_airtable_sync(self, contact_id: str, success: bool, record_type: str = "insight"):
        """Log Airtable synchronization"""
        if success:
            self.metrics.log_airtable_record()
            
        status = "✅" if success else "❌"
        self.logger.info(f"{status} Airtable sync ({record_type}) for {contact_id}")
        
    def log_file_creation(self, file_path: str, file_type: str = "insight"):
        """Log file creation"""
        self.metrics.log_file_created()
        self.logger.info(f"📁 Created {file_type} file: {file_path}")
        
    def log_claim_event(self, contact_id: str, event: str, key: str = ""):
        """Log local-claim lifecycle events (attempt, acquired, released, skipped)."""
        key_str = f" key={key}" if key else ""
        self.logger.info(f"🔒 CLAIM {event} for {contact_id}{key_str}")

    def log_dispatcher_wave(self, in_flight: int, capacity: int, offset: int, fetch_limit: int, scheduled_count: int):
        """Log a scheduling wave in the dispatcher."""
        self.logger.info(
            f"📡 WAVE in_flight={in_flight} capacity={capacity} offset={offset} fetch_limit={fetch_limit} scheduled={scheduled_count}"
        )

    def log_run_banner(self, run_id: str, workers: int, batch_size: int, selection_mode: str, start_iso: str):
        """Print a run banner with core parameters."""
        self.logger.info(
            f"RUN {run_id} | workers={workers} batch_size={batch_size} selection={selection_mode} start={start_iso}"
        )
        
    def get_final_report(self) -> Dict[str, Any]:
        """Generate final processing report"""
        metrics = self.metrics.get_current_metrics()
        
        # Add contact timing details
        contact_details = []
        for contact_id, timing in self.metrics.contact_timings.items():
            if 'duration' in timing:
                contact_details.append({
                    'contact_id': contact_id,
                    'success': timing.get('success', False),
                    'duration_seconds': timing['duration']
                })
                
        # Add ENI group timing details
        eni_group_details = list(self.metrics.eni_group_timings.values())
        
        report = {
            'summary_metrics': metrics,
            'contact_details': contact_details,
            'eni_group_details': eni_group_details,
            'log_files': {
                'main_log': str(self.log_dir / 'member_insights.log'),
                'error_log': str(self.log_dir / 'errors.log'),
                'metrics_log': str(self.log_dir / 'metrics.log'),
                'ai_log': str(self.log_dir / 'ai_processing.log'),
                'data_log': str(self.log_dir / 'data_processing.log')
            }
        }
        
        return report

def create_enhanced_logger(config: Dict[str, Any]) -> EnhancedLogger:
    """Factory function to create enhanced logger"""
    return EnhancedLogger(config) 