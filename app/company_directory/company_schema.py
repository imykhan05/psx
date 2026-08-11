COMPANY_COLUMNS = [
    "symbol",
    "company",
    "sector",
    "industry",
    "market",
    "status",
    "listing_date",
    "listing_year",
    "website",
    "remarks"
]


SECTOR_COLUMNS = [
    "sector",
    "sector_code",
    "description"
]


INDUSTRY_COLUMNS = [
    "industry",
    "sector",
    "description"
]


LISTING_COLUMNS = [
    "symbol",
    "listing_date",
    "listing_year",
    "status"
]


def get_company_columns():
    return COMPANY_COLUMNS


def get_sector_columns():
    return SECTOR_COLUMNS


def get_industry_columns():
    return INDUSTRY_COLUMNS


def get_listing_columns():
    return LISTING_COLUMNS


def empty_company_row():
    return {col: None for col in COMPANY_COLUMNS}