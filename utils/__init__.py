"""
NexusIQ AI — Utils Package
"""

# Only import what exists
from .validators import validate_question

# Try importing constants, but don't fail if they don't exist
try:
    from .validators import VALID_REGIONS, VALID_CATEGORIES
except ImportError:
    VALID_REGIONS = ['East', 'West', 'North', 'South', 'Central']
    VALID_CATEGORIES = ['Electronics', 'Clothing', 'Food', 'Home', 'Sports']

from .quota_tracker import get_tracker, QuotaTracker