"""
NexusIQ AI — Quota Tracker (Circuit Breaker Pattern)
Tracks model availability to skip dead models instantly
"""

import time
import json
import logging
from pathlib import Path
from typing import Dict, Tuple
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
    TRACKER_FILE = Path("data/quota_tracker.json")
    
    # How long to wait before retrying a failed model (in seconds)
    RETRY_DELAYS = {
        "RESOURCE_EXHAUSTED": 3600,   # 1 hour for quota exhaustion (429)
        "RATE_LIMIT": 60,              # 1 minute for RPM limit
        "DEADLINE_EXCEEDED": 300,      # 5 min for timeouts (504)
        "CONNECTION": 180,             # 3 min for connection errors
        "NOT_FOUND": 86400,            # 24 hours for model doesn't exist (404)
        "SERVER_ERROR": 300,           # 5 min for server errors (500/503)
        "DEFAULT": 300                 # 5 min for unknown errors
    }
    
    def __init__(self):
        # Ensure data directory exists
        self.TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing state or start fresh
        self.models = self._load_state()
        
        logger.info(f"📂 Quota tracker initialized: {len(self.models)} models tracked")
    
    def _load_state(self) -> Dict:
        """Load tracker state from file"""
        try:
            if self.TRACKER_FILE.exists():
                with open(self.TRACKER_FILE, 'r') as f:
                    data = json.load(f)
                    logger.info(f"📂 Loaded quota tracker state from {self.TRACKER_FILE}")
                    return data
        except Exception as e:
            logger.warning(f"⚠️ Could not load tracker state: {e}")
        
        return {}  # Return empty dict if file doesn't exist or error
    
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
        error_upper = error_message.upper()
        
        if "429" in error_message or "RESOURCE_EXHAUSTED" in error_upper or "QUOTA" in error_upper:
            return "RESOURCE_EXHAUSTED"
        elif "RATE" in error_upper and "LIMIT" in error_upper:
            return "RATE_LIMIT"
        elif "404" in error_message or "NOT FOUND" in error_upper:
            return "NOT_FOUND"
        elif "500" in error_message or "503" in error_message or "SERVER" in error_upper:
            return "SERVER_ERROR"
        elif "DEADLINE_EXCEEDED" in error_upper or "TIMEOUT" in error_upper or "504" in error_message:
            return "DEADLINE_EXCEEDED"
        elif "CONNECTION" in error_upper or "NETWORK" in error_upper:
            return "CONNECTION"
        else:
            return "DEFAULT"
    
    def is_available(self, model_name: str) -> Tuple[bool, str]:
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
                # Still in cooldown period
                remaining = (retry_time - now).total_seconds()
                minutes = int(remaining / 60)
                seconds = int(remaining % 60)
                
                error_type = model_info.get("error_type", "UNKNOWN")
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
        Report model failure with smart retry delays
        
        Args:
            model_name: Model identifier
            error_message: Error message from API
        """
        
        now = datetime.now()
        
        # Classify error type
        error_type = self._classify_error(error_message)
        retry_delay = self.RETRY_DELAYS.get(error_type, self.RETRY_DELAYS["DEFAULT"])
        retry_after = now + timedelta(seconds=retry_delay)
        
        logger.warning(f"🔴 {model_name}: {error_type}, retry in {retry_delay/60:.0f} min")
        
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
        now = datetime.now()
        
        for model_name, state in self.models.items():
            # Parse last failure time
            last_failure_str = state.get("last_failure")
            if last_failure_str:
                last_failure = datetime.fromisoformat(last_failure_str)
                time_since_failure = (now - last_failure).total_seconds()
            else:
                time_since_failure = 0
            
            # Parse retry time
            retry_after_str = state.get("retry_after")
            if retry_after_str:
                retry_after = datetime.fromisoformat(retry_after_str)
                retry_in = max(0, (retry_after - now).total_seconds())
            else:
                retry_in = 0
            
            # Determine status
            if retry_in > 0:
                status = "🔴 BLOCKED"
            else:
                status = "🟡 RETRY_READY"
            
            report[model_name] = {
                "status": status,
                "error_type": state.get("error_type", "UNKNOWN"),
                "failure_count": state.get("failure_count", 0),
                "failed_ago": f"{int(time_since_failure)}s",
                "retry_in": f"{int(retry_in)}s",
                "last_error": state.get("last_error", "")[:50]
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
#  GLOBAL TRACKER INSTANCE (SINGLETON)
# ═══════════════════════════════════════════════════════════

_tracker_instance = None

def get_tracker() -> QuotaTracker:
    """Get the global quota tracker instance"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = QuotaTracker()
    return _tracker_instance


# Alias for backward compatibility
quota_tracker = None  # Will be set on first import if needed

def _init_global():
    """Initialize global quota_tracker variable"""
    global quota_tracker
    if quota_tracker is None:
        quota_tracker = get_tracker()

_init_global()


# ═══════════════════════════════════════════════════════════
#  TESTING
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test the tracker
    tracker = get_tracker()
    
    print("\n" + "="*50)
    print("QUOTA TRACKER TEST")
    print("="*50 + "\n")
    
    # Test 1: Check fresh model availability
    print("Test 1: Check fresh model")
    available, reason = tracker.is_available("gemini-2.5-flash")
    print(f"  Gemini Flash available: {available}")
    print(f"  Reason: {reason}")
    
    # Test 2: Simulate quota exhaustion
    print("\nTest 2: Simulate quota exhaustion")
    tracker.report_failure("gemini-2.5-flash", "429 RESOURCE_EXHAUSTED: quota exceeded")
    available, reason = tracker.is_available("gemini-2.5-flash")
    print(f"  Gemini Flash available: {available}")
    print(f"  Reason: {reason}")
    
    # Test 3: Simulate timeout
    print("\nTest 3: Simulate timeout")
    tracker.report_failure("groq-llama", "504 DEADLINE_EXCEEDED")
    available, reason = tracker.is_available("groq-llama")
    print(f"  Groq Llama available: {available}")
    print(f"  Reason: {reason}")
    
    # Test 4: Get status report
    print("\nTest 4: Status Report")
    report = tracker.get_status_report()
    print(json.dumps(report, indent=2))
    
    # Test 5: Reset all
    print("\nTest 5: Reset all models")
    tracker.reset_all()
    available, reason = tracker.is_available("gemini-2.5-flash")
    print(f"  After reset - Gemini Flash available: {available}")
    
    print("\n" + "="*50)
    print("✅ Quota Tracker tests complete!")
    print("="*50 + "\n")