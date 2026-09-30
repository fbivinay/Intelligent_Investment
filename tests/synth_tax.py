"""Made-up round-number tax rules. They test the engine's logic, never real rates."""
from tests.helpers import table

OLD = '[ {upto = "250000", rate = "0"}, {upto = "500000", rate = "0.05"}, {upto = "1000000", rate = "0.20"}, {upto = "", rate = "0.30"} ]'
NEW = '[ {upto = "300000", rate = "0"}, {upto = "600000", rate = "0.05"}, {upto = "900000", rate = "0.10"}, {upto = "", rate = "0.30"} ]'
TIERS = '[ {above = "5000000", rate = "0.10"}, {above = "10000000", rate = "0.15"} ]'
# A top tier that looks at income without special-rate gains, as the 25% tier does in the real rules.
TIERS_TOP = ('[ {above = "5000000", rate = "0.10"}, {above = "10000000", rate = "0.15"}, '
             '{above = "20000000", rate = "0.25", basis = "excluding_special"} ]')
ASSUMED = 'source = "test fixture"\nverified_on = 2026-01-01\nconfidence = "assumed"\nnote = "test convention"'
LATE_NEW = 'late_keys = [{ regime = "new", from = 2020-04-01 }]'

EQ_COMMON = 'lt_months = 12\nst_treatment = "special"\nst_rate = "0.15"\nst_section = "111A"'
SLAB_LT20 = ('lt_months = 36\nst_treatment = "slab"\nst_section = "slab"\n'
             'lt_treatment = "special"\nlt_rate = "0.20"\nlt_section = "112"\nindexation = true')
# Until 2014-07-10 a unit could instead pay 10% on the gain without indexation.
SLAB_LT20_OR_10 = ('lt_months = 12\nst_treatment = "slab"\nst_section = "slab"\n'
                   'lt_treatment = "special"\nlt_rate = "0.20"\nlt_section = "112"\nindexation = true\n'
                   'lt_alt_rate = "0.10"\nlt_alt_indexation = false\nlt_alt_section = "112 (10% option)"')

TAX = {
    "tax.buckets": table(["asset_class"], [
        'asset_class = "etf_equity"\nfrom = 2010-04-01\nbucket = "equity"',
        'asset_class = "mf_equity"\nfrom = 2010-04-01\nbucket = "equity"',
        'asset_class = "etf_gold"\nfrom = 2010-04-01\nbucket = "gold"',
        'asset_class = "mf_debt"\nfrom = 2010-04-01\nto = 2023-03-31\nbucket = "debt_pre"',
        'asset_class = "mf_debt"\nfrom = 2023-04-01\nbucket = "debt_post"',
    ]),
    "tax.capital_gains": table(["bucket"], [
        f'bucket = "equity"\nfrom = 2010-04-01\nto = 2018-03-31\n{EQ_COMMON}\nlt_treatment = "exempt"\nlt_section = "10(38)"',
        f'bucket = "equity"\nfrom = 2018-04-01\n{EQ_COMMON}\nlt_treatment = "special"\nlt_rate = "0.10"\nlt_section = "112A"\n'
        'lt_exemption_group = "112a"\ngrandfather_acq_upto = 2018-01-31',
        f'bucket = "gold"\nfrom = 2010-04-01\nto = 2014-07-10\n{SLAB_LT20_OR_10}',
        f'bucket = "gold"\nfrom = 2014-07-11\n{SLAB_LT20}',
        f'bucket = "debt_pre"\nfrom = 2010-04-01\n{SLAB_LT20}',
        # section 50AA: deemed short-term, so the row has no holding period and no long-term fields
        'bucket = "debt_post"\nfrom = 2010-04-01\nalways_short = true\nst_treatment = "slab"\nst_section = "50AA"',
    ]),
    # Two series: 1981 base for sales up to 2017-03-31, 2001 base after. Values differ so a test can tell which one was read.
    "tax.cii": table(["series"], [
        f'series = "1981"\nfrom = {fy}-04-01\nto = {fy + 1}-03-31\nvalue = "{500 + 20 * (fy - 2010)}"' for fy in range(2010, 2017)
    ] + [
        f'series = "2001"\nfrom = {fy}-04-01\n' + (f'to = {fy + 1}-03-31\n' if fy < 2025 else '') + f'value = "{200 + 10 * (fy - 2010)}"'
        for fy in range(2010, 2026)
    ], extra_meta="open_ended = false"),
    "tax.lt_exemption": table(["group"], [
        'group = "112a"\nfrom = 2010-04-01\nto = 2024-03-31\nvalue = "100000"\norder = "lowest_rate_first"',
        'group = "112a"\nfrom = 2024-04-01\nvalue = "125000"\norder = "lowest_rate_first"',
    ]),
    "tax.slabs": table(["regime"], [
        f'regime = "old"\nfrom = 2010-04-01\nbrackets = {OLD}',
        f'regime = "new"\nfrom = 2020-04-01\nbrackets = {NEW}',
    ], extra_meta=LATE_NEW),
    "tax.rebate_87a": table(["regime"], [
        'regime = "old"\nfrom = 2010-04-01\nincome_limit = "500000"\nmax_rebate = "12500"\napplies_to_special = true\n'
        'excluded_sections = ["112A"]',
        'regime = "new"\nfrom = 2020-04-01\nincome_limit = "700000"\nmax_rebate = "25000"\n'
        'applies_to_special = false\nmarginal_relief = true',
    ], extra_meta=LATE_NEW),
    "tax.surcharge": table(["regime"], [
        f'regime = "old"\nfrom = 2010-04-01\ntiers = {TIERS_TOP}\ncap_special = "0.15"\ncap_sections = ["111A"]',
        f'regime = "new"\nfrom = 2020-04-01\ntiers = {TIERS}\ncap_special = "0.15"',
    ], extra_meta=LATE_NEW),
    "tax.cess": table([], ['from = 2010-04-01\nvalue = "0.04"']),
    "tax.dividend": table([], [
        'from = 2010-04-01\nto = 2016-03-31\nmode = "exempt"',
        'from = 2016-04-01\nto = 2020-03-31\nmode = "above_threshold"\nthreshold = "1000000"\nrate = "0.10"',
        'from = 2020-04-01\nmode = "slab"',
    ]),
    "tax.loss_rules": table(["kind"], [
        'kind = "capital"\nfrom = 2010-04-01\nvalue = "8"',
        'kind = "business"\nfrom = 2010-04-01\nvalue = "8"',
    ]),
    "tax.audit": table([], ['from = 2010-04-01\nturnover_limit = "10000000"\nfee = "25000"']),
    "tax.conventions": table(["name"], [
        f'name = "setoff_order"\nfrom = 2010-04-01\nvalue = "as coded"\n{ASSUMED}',
        f'name = "shortfall_order"\nfrom = 2010-04-01\nvalue = "as coded"\n{ASSUMED}',
        f'name = "business_loss_setoff"\nfrom = 2010-04-01\nvalue = "slab income only"\n{ASSUMED}',
        f'name = "marginal_relief_order"\nfrom = 2010-04-01\nvalue = "as coded"\n{ASSUMED}',
        'name = "tax_round_step"\nfrom = 2010-04-01\nvalue = "10"',
    ]),
}
