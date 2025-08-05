# Airtable_Affiliations - Default Context

## Data Source Overview
- **ENI Source Type**: airtable_affiliations
- **Primary Purpose**: Track member professional, educational, and organizational affiliations
- **Data Quality**: High reliability - manually curated from verified sources

## Data Generation Pattern
```
[Member] is affiliated with [Entity] as a [Affiliation Type] sub affiliation type: [Position]. 
[Entity] is a [Entity Category] described by [Entity Description]. 
Tags: [Sectors] [Asset Classes] [Strategies]
```

## Categorization Guidelines

### Personal Section
- Educational affiliations (universities, alumni associations)
- Charitable organizations and non-profits
- Cultural/social organizations, foundations

**Format for Personal:**
- Schools/universities: "Graduated from [University Name]" or "Alumni of [School Name]"
- Charities/Non-profits: "Board member/supporter of [Organization Name]"
- Cultural organizations: "Member of [Organization Name]"

### Business Section  
- Employment history and current roles
- Professional board memberships and advisory positions
- Industry organizations and trade groups

**Format for Professional:**
- Current role: "[Title] at [Firm] ([sectors - both directly noted and assumed from entity description])"
- Former roles: "Former [Title] at [Firm] ([sectors])"
- List roles chronologically when possible, newest first
- Include both explicit sector tags and sectors inferred from entity descriptions
- Board positions: "Board member at [Company] ([sectors])"

### Investing Section
- Investment fund affiliations and portfolio companies
- Angel investor groups and investment-focused board roles

**Format for Investing:**
- "[Role] at [Fund/Investment Entity] ([asset classes/strategies])"
- Portfolio company connections: "Portfolio company experience with [Company] ([sectors])"

## Expertise Interpretation
- **Sector Expertise**: Affiliations indicate expertise in those sectors
- **Operational Experience**: Employment/leadership roles show hands-on knowledge
- **Investment Experience**: Fund/portfolio company connections indicate investment expertise
- **Network Access**: Affiliations suggest potential deal flow and connections

## Priority Information
1. **Current Leadership Roles**: CEO, Founder, Managing Partner positions
2. **Board Memberships**: Governance experience and sector expertise
3. **Prestigious Affiliations**: Well-known companies, top universities, notable organizations
4. **Sector Clustering**: Multiple affiliations in same industry indicate deep expertise
5. **Investment Connections**: Fund, portfolio company, or angel group affiliations

## Processing Instructions
- Group sectors from multiple affiliations to identify core expertise areas
- Note career progression from education through professional roles
- Consider how affiliations support investment interests and deal sourcing capability
- Identify networks accessible through various affiliations for introduction potential
