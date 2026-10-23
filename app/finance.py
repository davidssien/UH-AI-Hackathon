"""True monthly cost of owning a home. All rates are USER INPUTS — we never assert a current mortgage rate."""


def monthly_cost(price, rate_pct, down_pct=10.0, term_years=30, tax_pct=2.2, insurance_yr=None,
                 hoa_mo=0.0, flood_yr=0.0, pmi_pct=0.5):
    """-> dict of monthly components. insurance_yr defaults to 1% of price/yr (an assumption; edit it)."""
    down = price * down_pct / 100
    loan = price - down  # works on scalars and numpy arrays (persona mode scores every listing at once)
    r, n = rate_pct / 100 / 12, int(term_years * 12)
    pi = loan / n if r == 0 else loan * r * (1 + r) ** n / ((1 + r) ** n - 1)
    ins = price * 0.01 if insurance_yr is None else insurance_yr
    out = {
        "principal_interest": pi,
        "property_tax": price * tax_pct / 100 / 12,
        "insurance": ins / 12,
        "hoa": hoa_mo or 0.0,
        "flood": (flood_yr or 0.0) / 12,
        "pmi": loan * pmi_pct / 100 / 12 if down_pct < 20 else 0.0,
    }
    out["total"] = sum(out.values())
    out["down_payment"], out["loan"] = down, loan
    return out


def affordability(total_monthly, annual_income):
    """-> (share of gross monthly income, 'green' <= 30%, 'yellow' <= 36%, else 'red')."""
    share = total_monthly / (annual_income / 12) * 100 if annual_income > 0 else float("inf")
    return share, "green" if share <= 30 else "yellow" if share <= 36 else "red"
