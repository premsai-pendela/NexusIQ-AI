"""
NexusIQ AI — Quota Tracker (Circuit Breaker Pattern)
Tracks model availability to skip dead models instantly
"""

import time
import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  QUOTA TRACKER CLASS
# ═══════════════════════════════════════════════════════════

class QuotaTracker:
    """
    Tracks which LLM models have hit quota limits.
    Prevents wasting 30-60 seconds on models we know will fail.
    
    Circuit Breaker Pattern:
      - CLOSED (🟢): Model is working, try it
      - OPEN (🔴): Model failed recently, skip it
      - HALF-OPEN (🟡): Enough time passed, try again
    """
    
    # File to persist tracker across restarts
    TRACKER_FILE = Path(__file__).parent.parent / "data" / "quota_tracker.json"
    
    # How long to wait before retrying a failed model
    RETRY_DELAYS = {
        "quota_exceeded": 3600,      # 1 hour (daily quota)
        "rate_limit": 60,            # 1 minute (RPM limit)
        "server_error": 300,         # 5 minutes (temporary issue)
        "not_found": 86400,          # 24 hours (model doesn't exist)
        "connection_error": 120,     # 2 minutes (network issue)
        "unknown": 300               # 5 minutes (default)
    }
    
    def __init__(self):
        self.state_file = Path("data/quota_tracker.json")
        self.state_file.parent.mkdir(exist_ok=True)
        
        # ✅ UPDATED: Different retry delays for different errors
        self.RETRY_DELAYS = {
            "RESOURCE_EXHAUSTED": 3600,  # 1 hour for quota exhaustion (429)
            "DEADLINE_EXCEEDED": 300,    # 5 min for timeouts (504)
            "CONNECTION": 180,           # 3 min for connection errors
            "DEFAULT": 300               # 5 min for unknown errors
        }
        
        self.models = self._load_state() or {}
        logger.info(f"📂 Loaded quota tracker state: {len(self.models)} models tracked")
    
    def _load_state(self):
        """Load tracker state from file"""
        try:
            if self.TRACKER_FILE.exists():
                with open(self.TRACKER_FILE, 'r') as f:
                    self.models = json.load(f)
                logger.info(f"📂 Loaded quota tracker state: {len(self.models)} models tracked")
        except Exception as e:
            logger.warning(f"⚠️ Could not load tracker state: {e}")
            self.models = {}
    
    def _save_state(self):
        """Save tracker state to file"""
        try:
            self.TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.TRACKER_FILE, 'w') as f:
                json.dump(self.models, f, indent=2)
        except Exception as e:
            logger.warning(f"⚠️ Could not save tracker state: {e}")
    
    def _classify_error(self, error_message: str) -> str:
        """Classify error type from error message"""
        error_lower = error_message.lower()
        
        if "429" in error_message or "quota" in error_lower or "exhausted" in error_lower:
            return "quota_exceeded"
        elif "rate" in error_lower and "limit" in error_lower:
            return "rate_limit"
        elif "404" in error_message or "not found" in error_lower:
            return "not_found"
        elif "500" in error_message or "503" in error_message or "server" in error_lower:
            return "server_error"
        elif "connection" in error_lower or "timeout" in error_lower:
            return "connection_error"
        else:
            return "unknown"
    
    def is_available(self, model_name: str) -> tuple:
        """
        Check if model is available for use
        
        Returns:
            (is_available: bool, reason: str)
        """
        
        if model_name not in self.models:
            return True, "No tracking data"
        
        model_info = self.models[model_name]
        
        if model_info.get("status") != "FAILED":
            return True, "Model is available"
        
        # Check retry time
        retry_after = model_info.get("retry_after")
        if retry_after:
            retry_time = datetime.fromisoformat(retry_after)
            now = datetime.now()
            
            if now < retry_time:
                # ✅ FIXED: Show remaining wait time
                remaining = (retry_time - now).total_seconds()
                minutes = int(remaining / 60)
                seconds = int(remaining % 60)
                
                error_type = model_info.get("error_type", "unknown")
                return False, f"{error_type}: Retry in {minutes}m {seconds}s"
            else:
                # Retry time reached - reset status
                logger.info(f"🟡 {model_name}: Retry time reached, resetting to available")
                model_info["status"] = "AVAILABLE"
                model_info["failure_count"] = 0
                self._save_state()
                return True, "Retry time reached"
        
        return True, "No retry time set"
    
    def report_success(self, model_name: str):
        """Mark model as working (CLOSED state)"""
        if model_name in self.models:
            del self.models[model_name]
            self._save_state()
            logger.info(f"🟢 {model_name}: Marked as ACTIVE")
    
    def report_failure(self, model_name: str, error_message: str):
        """
        ✅ FIXED: Report model failure with smart retry delays
        
        Args:
            model_name: Model identifier
            error_message: Error message from API
        """
        
        now = datetime.now()
        
        # Determine error type and retry delay
        error_upper = error_message.upper()
        
        if "RESOURCE_EXHAUSTED" in error_upper or "429" in error_message:
            error_type = "RESOURCE_EXHAUSTED"
            retry_delay = self.RETRY_DELAYS["RESOURCE_EXHAUSTED"]  # 1 hour
            logger.warning(f"🔴 {model_name}: Quota exhausted, retry in {retry_delay/60:.0f} min")
        
        elif "DEADLINE_EXCEEDED" in error_upper or "504" in error_message or "TIMEOUT" in error_upper:
            error_type = "DEADLINE_EXCEEDED"
            retry_delay = self.RETRY_DELAYS["DEADLINE_EXCEEDED"]  # 5 min
            logger.warning(f"🟡 {model_name}: Timeout, retry in {retry_delay/60:.0f} min")
        
        elif "CONNECTION" in error_upper or "NETWORK" in error_upper:
            error_type = "CONNECTION"
            retry_delay = self.RETRY_DELAYS["CONNECTION"]  # 3 min
            logger.warning(f"🟠 {model_name}: Connection issue, retry in {retry_delay/60:.0f} min")
        
        else:
            error_type = "UNKNOWN"
            retry_delay = self.RETRY_DELAYS["DEFAULT"]  # 5 min
            logger.warning(f"⚫ {model_name}: Unknown error, retry in {retry_delay/60:.0f} min")
        
        retry_after = now + timedelta(seconds=retry_delay)
        
        if model_name not in self.models:
            self.models[model_name] = {
                "status": "FAILED",
                "last_failure": now.isoformat(),
                "failure_count": 1,
                "retry_after": retry_after.isoformat(),
                "last_error": error_message[:200],
                "error_type": error_type
            }
        else:
            self.models[model_name].update({
                "status": "FAILED",
                "last_failure": now.isoformat(),
                "failure_count": self.models[model_name].get("failure_count", 0) + 1,
                "retry_after": retry_after.isoformat(),
                "last_error": error_message[:200],
                "error_type": error_type
            })
        
        self._save_state()
    
    def get_status_report(self) -> Dict[str, dict]:
        """Get current status of all tracked models"""
        report = {}
        
        for model_name, state in self.models.items():
            failed_at = state.get("failed_at", 0)
            error_type = state.get("error_type", "unknown")
            retry_delay = self.RETRY_DELAYS.get(error_type, 300)
            time_since_failure = time.time() - failed_at
            
            if time_since_failure >= retry_delay:
                status = "🟡 RETRY_READY"
            else:
                status = "🔴 BLOCKED"
            
            report[model_name] = {
                "status": status,
                "error_type": error_type,
                "failed_ago": f"{int(time_since_failure)}s",
                "retry_in": f"{max(0, int(retry_delay - time_since_failure))}s"
            }
        
        return report
    
    def reset_model(self, model_name: str):
        """Manually reset a model's status"""
        if model_name in self.models:
            del self.models[model_name]
            self._save_state()
            logger.info(f"🔄 {model_name}: Manually reset to ACTIVE")
    
    def reset_all(self):
        """Reset all models to active state"""
        self.models = {}
        self._save_state()
        logger.info("🔄 All models reset to ACTIVE")


# ═══════════════════════════════════════════════════════════
#  GLOBAL TRACKER INSTANCE
# ═══════════════════════════════════════════════════════════

# Singleton instance
_tracker_instance = None

def get_tracker() -> QuotaTracker:
    """Get the global quota tracker instance"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = QuotaTracker()
    return _tracker_instance


# ═══════════════════════════════════════════════════════════
#  TESTING
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test the tracker
    tracker = get_tracker()
    
    print("\n=== Quota Tracker Test ===\n")
    
    # Test availability check
    available, reason = tracker.is_available("gemini-2.5-pro")
    print(f"Gemini available: {available}, Reason: {reason}")
    
    # Simulate failure
    tracker.report_failure("gemini-2.5-pro", "429 RESOURCE_EXHAUSTED quota exceeded")
    
    # Check again
    available, reason = tracker.is_available("gemini-2.5-pro")
    print(f"Gemini available after failure: {available}, Reason: {reason}")
    
    # Get status report
    print("\nStatus Report:")
    print(json.dumps(tracker.get_status_report(), indent=2))
    
    # Reset
    tracker.reset_all()
    print("\nAfter reset - all models available")
