# utils.py
from datetime import datetime

def should_mark_completed(status, description):
    """
    Determines if a lead should be marked as completed based on positive conversion only.
    
    Args:
        status (str): Current lead status
        description (str): Lead description or notes
        
    Returns:
        tuple: (bool, str) - (should_complete, final_status)
    """
    # Convert status to uppercase and description to lowercase for matching
    status = status.upper()
    description = description.lower() if description else ''
    
    # Only BOOKING_DONE is considered positive completion
    if status == 'BOOKING_DONE':
        return True, status
    
    # Check description for positive completion keywords only
    positive_keywords = {
        'booking done': 'BOOKING_DONE',
        'booked': 'BOOKING_DONE',
        'deal closed': 'BOOKING_DONE',
        'payment received': 'BOOKING_DONE'
    }
    
    for keyword, new_status in positive_keywords.items():
        if keyword in description:
            return True, new_status
            
    return False, status