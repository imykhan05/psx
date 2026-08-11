from pathlib import Path

base = Path("database/psx_intelligence")
base.mkdir(parents=True, exist_ok=True)

companies = """symbol,company,sector,industry,market,status,listing_date,listing_year,website,source,remarks
ASTL,Amreli Steels,STEEL,STEEL MANUFACTURING,REGULAR,ACTIVE,,,https://amrelisteels.com,SEED,
AGHA,Agha Steel Industries,STEEL,STEEL MANUFACTURING,REGULAR,ACTIVE,,,https://aghasteel.com,SEED,
ASL,Aisha Steel Mills,STEEL,STEEL MANUFACTURING,REGULAR,ACTIVE,,,https://aishasteel.com,SEED,
MUGHAL,Mughal Iron & Steel,STEEL,STEEL MANUFACTURING,REGULAR,ACTIVE,,,https://mughalsteel.com,SEED,
ITTEFAQ,Ittefaq Iron Industries,STEEL,STEEL MANUFACTURING,REGULAR,ACTIVE,,,https://ittefaqsteel.com,SEED,
INIL,International Industries,STEEL,STEEL PIPES,REGULAR,ACTIVE,,,https://iil.com.pk,SEED,
HBL,Habib Bank,BANKS,COMMERCIAL BANKS,REGULAR,ACTIVE,,,https://hbl.com,SEED,
UBL,United Bank,BANKS,COMMERCIAL BANKS,REGULAR,ACTIVE,,,https://ubldigital.com,SEED,
MCB,MCB Bank,BANKS,COMMERCIAL BANKS,REGULAR,ACTIVE,,,https://mcb.com.pk,SEED,
MEBL,Meezan Bank,BANKS,ISLAMIC BANKING,REGULAR,ACTIVE,,,https://meezanbank.com,SEED,
NBP,National Bank,BANKS,COMMERCIAL BANKS,REGULAR,ACTIVE,,,https://nbp.com.pk,SEED,
SNBL,Soneri Bank,BANKS,COMMERCIAL BANKS,REGULAR,ACTIVE,,,https://soneribank.com,SEED,
JSBL,JS Bank,BANKS,COMMERCIAL BANKS,REGULAR,ACTIVE,,,https://jsbl.com,SEED,
BIPL,BankIslami Pakistan,BANKS,ISLAMIC BANKING,REGULAR,ACTIVE,,,https://bankislami.com.pk,SEED,
BAFL,Bank Alfalah,BANKS,COMMERCIAL BANKS,REGULAR,ACTIVE,,,https://bankalfalah.com,SEED,
BAHL,Bank AL Habib,BANKS,COMMERCIAL BANKS,REGULAR,ACTIVE,,,https://bankalhabib.com,SEED,
EFERT,Engro Fertilizers,FERTILIZER,FERTILIZER,REGULAR,ACTIVE,,,https://engrofertilizers.com,SEED,
FFC,Fauji Fertilizer,FERTILIZER,FERTILIZER,REGULAR,ACTIVE,,,https://ffc.com.pk,SEED,
ENGRO,Engro Corporation,CHEMICAL,CONGLOMERATE,REGULAR,ACTIVE,,,https://engro.com,SEED,
LUCK,Lucky Cement,CEMENT,CEMENT,REGULAR,ACTIVE,,,https://lucky-cement.com,SEED,
DGKC,D.G. Khan Cement,CEMENT,CEMENT,REGULAR,ACTIVE,,,https://dgcement.com,SEED,
THCCL,Thatta Cement,CEMENT,CEMENT,REGULAR,ACTIVE,,,https://thattacement.com,SEED,
CHCC,Cherat Cement,CEMENT,CEMENT,REGULAR,ACTIVE,,,https://gfg.com.pk,SEED,
PICT,Pakistan International Container Terminal,TRANSPORT,PORTS,REGULAR,ACTIVE,,,https://pict.com.pk,SEED,
PIBTL,Pakistan International Bulk Terminal,TRANSPORT,PORTS,REGULAR,ACTIVE,,,https://pibt.com.pk,SEED,
BLUEX,Blue-Ex,TRANSPORT,LOGISTICS,REGULAR,ACTIVE,,,https://blue-ex.com,SEED,
TPLP,TPL Properties,REAL_ESTATE,REAL ESTATE,REGULAR,ACTIVE,,,https://tplproperties.com,SEED,
TPLRF1,TPL REIT Fund I,REAL_ESTATE,REIT,REGULAR,ACTIVE,,,,SEED,
PACE,Pace Pakistan,REAL_ESTATE,REAL ESTATE,REGULAR,ACTIVE,,,,SEED,
LSECL,LSE Capital,INVESTMENT,INVESTMENT,REGULAR,ACTIVE,,,,SEED,
LSEVL,LSE Ventures,INVESTMENT,INVESTMENT,REGULAR,ACTIVE,,,,SEED,
NEXT,Next Capital,INVESTMENT,BROKERAGE,REGULAR,ACTIVE,,,https://nextcapital.com.pk,SEED,
MACTER,Macter International,PHARMA,PHARMACEUTICALS,REGULAR,ACTIVE,,,https://macter.com,SEED,
SEARL,The Searle Company,PHARMA,PHARMACEUTICALS,REGULAR,ACTIVE,,,https://searlecompany.com,SEED,
IBLHL,IBL HealthCare,PHARMA,HEALTHCARE,REGULAR,ACTIVE,,,https://iblhealthcare.com,SEED,
CPHL,Citi Pharma,PHARMA,PHARMACEUTICALS,REGULAR,ACTIVE,,,https://citipharma.com.pk,SEED,
PINL,Premier Insurance,INSURANCE,GENERAL INSURANCE,REGULAR,ACTIVE,,,,SEED,
HICL,Habib Insurance,INSURANCE,GENERAL INSURANCE,REGULAR,ACTIVE,,,,SEED,
NICL,Nimir Industrial Chemicals,CHEMICAL,CHEMICALS,REGULAR,ACTIVE,,,https://nimir.com.pk,SEED,
"""

sectors = """sector,sector_code,industry_group,description
BANKS,BANK,FINANCIALS,Commercial and Islamic banks
STEEL,STL,MATERIALS,Steel and engineering products
CEMENT,CEM,MATERIALS,Cement manufacturers
FERTILIZER,FERT,CHEMICALS,Fertilizer companies
CHEMICAL,CHEM,CHEMICALS,Chemical and industrial chemical companies
PHARMA,PHRM,HEALTHCARE,Pharmaceutical and healthcare companies
TRANSPORT,TRNS,INDUSTRIALS,Transport logistics ports and terminals
REAL_ESTATE,RE,REAL ESTATE,Real estate and REITs
INVESTMENT,INV,FINANCIALS,Investment companies and brokerage
INSURANCE,INS,FINANCIALS,Insurance companies
UNKNOWN,UNK,UNKNOWN,Unmapped sector
"""

(base / "psx_companies.csv").write_text(companies, encoding="utf-8")
(base / "sector_dictionary.csv").write_text(sectors, encoding="utf-8")

print("PSX intelligence seed data created")