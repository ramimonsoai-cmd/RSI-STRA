# נתוני שווי שוק משוערים במיליארדים (גיבוי מיידי שמונע חסימות רשת)
ESTIMATED_MARKET_CAPS = {
    "MSFT": 3100, "AAPL": 3400, "NVDA": 3000, "GOOGL": 2000, "AMZN": 1950,
    "META": 1300, "BRK-B": 950, "TSLA": 750, "LLY": 850, "AVGO": 800,
    "JPM": 600, "WMT": 550, "V": 520, "XOM": 470, "MA": 430, "UNH": 530,
    "ORCL": 380, "COST": 370, "HD": 360, "PG": 380, "BAC": 310, "JNJ": 380,
    "ABBV": 310, "CVX": 270, "MRK": 280, "NFLX": 290, "KO": 270, "AMD": 240,
    "PEP": 230, "TMO": 220, "LIN": 220, "CSCO": 200, "ADBE": 220, "MCD": 210,
    "DIS": 180, "WFC": 190, "INTU": 180, "CAT": 170, "IBM": 170, "GE": 180
}

def get_tickers_by_market_cap(universe, min_billions):
    """מסנן מניות בצורה מהירה ואמינה ללא חסימות Yahoo Finance"""
    passed = []
    min_cap_usd = min_billions * 1_000_000_000
    
    for sym in universe:
        cap = None
        try:
            # בדיקה ראשונה דרך fast_info המהיר
            t = yf.Ticker(sym)
            cap = getattr(t.fast_info, 'market_cap', None)
        except Exception:
            pass
            
        # אם יש חסימה של Yahoo, משתמשים במאגר המגובה
        if not cap and sym in ESTIMATED_MARKET_CAPS:
            cap = ESTIMATED_MARKET_CAPS[sym] * 1_000_000_000
            
        if cap and cap >= min_cap_usd:
            passed.append(sym)
            
    return passed
