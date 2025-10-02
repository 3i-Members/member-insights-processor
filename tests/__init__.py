"""
Test package for Member Insights Processor

This package contains all unit tests, integration tests, and utility tests
for the member insights processing system.
"""

# Shared test constants
DEFAULT_CONTACT_ID = "CNT-HvA002554"

# Default structured insight used when no current summary exists in Supabase (for tests)
DEFAULT_STRUCTURED_INSIGHT = {
    "personal": "* Enjoys music, reading, skiing/snowboarding, and tennis\n  * [2024-01-15,ENI-123456]\n  * [2024-02-10,ENI-123457]\n* Recently relocated to Austin, TX for proximity to energy sector opportunities\n  * [2024-03-01,ENI-234567]",
    "business": "* Current role as Managing Partner at TechVentures ($250M AUM)\n  * [2024-01-20,ENI-345678]\n* 15 years experience in B2B software scaling\n  * [2023-12-15,ENI-456789]",
    "investing": "* Active angel investor in AI/ML startups ($50K-$250K checks)\n  * [2024-02-01,ENI-567890]\n  * [2024-01-10,ENI-678901]\n* Focus on Series A SaaS companies with $2M+ ARR\n  * [2024-02-15,ENI-789012]\n* Recently joined $50M growth equity fund as LP\n  * [2024-03-10,ENI-890123]",
    "3i": "* Member since Q2 2023\n  * [2023-06-01,ENI-901234]\n* Participated in 3 deal syndications totaling $15M\n  * [2024-01-05,ENI-012345]\n  * [2024-02-20,ENI-123456]\n* Active in Austin chapter events\n  * [2024-03-15,ENI-234567]",
    "deals": "This Member **Has Experience** and Is Comfortable Diligencing These Asset Classes & Sectors\n- Series A B2B SaaS ($2M-$15M revenue)\n  * [2024-01-10,ENI-345678]\n  * [2023-11-20,ENI-456789]\n- Southeast multifamily real estate\n  * [2024-02-05,ENI-567890]\n- AI/ML infrastructure companies\n  * [2024-01-25,ENI-678901]\n\nThis Member **Is Interested In Exploring** These Asset Classes, Sectors, and Strategies\n- Energy transition infrastructure funds\n  * [2024-03-01,ENI-789012]\n- Healthcare AI companies with FDA approval pathway\n  * [2024-02-28,ENI-890123]\n- Texas-based industrial real estate ($10M+ deals)\n  * [2024-03-10,ENI-901234]\n\nThis Member **Wants to Avoid** These Asset Classes, Sectors, and Strategies\n- Consumer social applications\n  * [2024-01-15,ENI-012345]\n- Pre-revenue biotech\n  * [2023-12-20,ENI-123456]\n- International emerging markets\n  * [N/A,ENI-234567]",
    "introductions": "**Looking to meet:**\n- Series B+ fintech CEOs seeking growth capital\n  * [2024-02-10,ENI-345678]\n  * [2024-01-30,ENI-456789]\n- Energy infrastructure fund GPs with $100M+ AUM\n  * [2024-03-05,ENI-567890]\n- Austin-based real estate developers in industrial/logistics\n  * [2024-02-25,ENI-678901]\n\n**Avoid introductions to:**\n- Early-stage consumer app founders\n  * [2024-01-20,ENI-789012]\n- Service providers without investment track record\n  * [2023-11-15,ENI-890123]\n- International deals outside North America\n  * [N/A,ENI-901234]",
}

__all__ = [
    "DEFAULT_CONTACT_ID",
    "DEFAULT_STRUCTURED_INSIGHT",
]
