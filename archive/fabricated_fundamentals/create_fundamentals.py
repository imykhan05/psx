from pathlib import Path

data = """symbol,eps,book_value,roe,roa,debt_equity,current_ratio,net_margin,revenue_growth,profit_growth,eps_growth,dividend_yield,dividend_years,payout_ratio,pe,pb,fair_value,margin_of_safety,listing_years,is_sector_leader,stable_earnings,low_debt,consistent_dividend
HBL,26.50,210.00,23.0,2.1,0.42,1.60,29.5,14.2,18.4,17.1,11.5,15,42,7.9,1.52,385,18,34,1,1,1,1
UBL,24.20,198.00,22.5,2.0,0.38,1.55,28.2,13.5,17.2,15.8,10.8,14,44,8.3,1.48,365,16,30,1,1,1,1
MEBL,31.70,240.00,27.3,2.6,0.35,1.74,33.8,18.4,20.2,21.1,9.2,12,39,7.1,1.44,470,20,27,1,1,1,1
ENGRO,34.80,305.00,25.1,8.4,0.59,1.90,18.7,16.8,19.6,18.8,8.4,10,48,8.8,1.71,420,17,32,1,1,1,1
EFERT,19.30,122.00,28.2,11.1,0.31,2.10,25.1,12.9,15.7,14.6,13.2,13,51,7.5,1.63,235,21,16,1,1,1,1
LUCK,52.60,455.00,21.4,9.3,0.48,1.72,17.3,15.1,18.7,16.5,4.2,8,34,9.5,1.82,980,14,30,1,1,1,1
DGKC,18.90,142.00,16.7,5.2,0.67,1.40,12.4,10.8,11.5,12.0,2.4,4,33,10.9,1.65,275,12,28,1,1,0,0
MCB,39.40,286.00,24.9,2.5,0.37,1.66,31.6,13.8,16.4,17.3,10.7,15,45,7.8,1.49,445,19,31,1,1,1,1
NBP,15.80,102.00,18.5,1.8,0.61,1.43,20.5,9.4,10.7,11.2,8.3,11,40,8.5,1.28,255,15,76,1,1,1,1
FFC,17.40,168.00,30.8,14.5,0.22,2.30,29.1,11.4,13.2,12.6,15.6,18,56,8.1,1.56,290,18,39,1,1,1,1
"""

Path("database/fundamentals").mkdir(parents=True, exist_ok=True)
Path("database/fundamentals/fundamentals.csv").write_text(data, encoding="utf-8")

print("fundamentals.csv created successfully")