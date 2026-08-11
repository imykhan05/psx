PSX_COMPANY_COLUMNS = [
    "symbol",
    "company",
    "sector",
    "industry",
    "market",
    "status",
    "listing_date",
    "listing_year",
    "website",
    "source",
    "remarks",
]

SECTOR_DICTIONARY_COLUMNS = [
    "sector",
    "sector_code",
    "industry_group",
    "description",
]


def get_psx_company_columns():
    return PSX_COMPANY_COLUMNS


def get_sector_dictionary_columns():
    return SECTOR_DICTIONARY_COLUMNS


def empty_psx_company_row():
    return {col: None for col in PSX_COMPANY_COLUMNS}