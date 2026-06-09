# MORTGAGE-CALC Business Rules Document

| | |
|---|---|
| **Program** | MORTGAGE-CALC |
| **Description** | UK Mortgage Amortisation Calculator |
| **Original language** | COBOL (1987-03-14) |
| **Migrated to** | Python (2026-05-25) |
| **Version** | 1.0.0 |

---

## 1. Who Should Read This Document

This document is written for **non-technical readers** who need to
understand or influence how the mortgage calculator works.

**Intended audience:**
- **Business Analysts** -- who need to verify the calculator behaves
  correctly for different mortgage products
- **Compliance Officers** -- who need to confirm regulatory rules are
  correctly encoded (e.g. early repayment penalties, rounding rules)
- **Regulators** -- who may audit the logic against published
  conduct rules
- **Product Managers** -- who want to propose changes (e.g. new
  penalty rates, additional rate types)

You do **not** need to read Python code to understand this document.
Every rule is explained in plain English.

---

## 2. What This Program Does

The Mortgage Amortisation Calculator works out:

1. **Your fixed monthly payment** -- the amount you pay every month
   for the life of the mortgage
2. **How much of each payment is interest vs. principal** -- in the
   early years, most of your payment is interest; in later years,
   most goes toward paying off the loan
3. **Your remaining balance** -- how much you still owe after any
   given month
4. **Total cost over the full term** -- the sum of all payments
   you will make
5. **Early repayment penalty** -- a charge that may apply if you
   pay off a fixed-rate mortgage early

---

## 3. How Your Monthly Payment Is Calculated

The calculator uses the **standard amortisation formula** -- the same
method used by virtually all UK mortgage lenders since the 1980s.

### The Formula (in plain English)

Your monthly payment is calculated so that, if you make every payment
on time, the loan is fully repaid at the end of the term. The formula
takes into account:

- How much you borrowed (the **principal**)
- The annual interest rate (e.g. 5.25% per year)
- How long the mortgage runs (the **term**, in years)

The annual rate is first divided by 12 to get a **monthly interest
rate**. Then the formula works out the fixed payment that will clear
the debt over all those months.

### Mathematical Formula

```
M = P x r(1+r)^n / ((1+r)^n - 1)
```

Where:

| Symbol | Meaning |
|--------|---------|
| **M** | Monthly repayment amount |
| **P** | Principal (amount borrowed) |
| **r** | Monthly interest rate (annual rate / 12) |
| **n** | Total number of monthly payments (term in years x 12) |

### Rounding

All calculations are rounded to **2 decimal places** (penny accuracy).
The rounding method is **ROUND_HALF_UP** -- this means 0.005 rounds
up to 0.01. This matches the rounding behaviour of the original COBOL
system and complies with **FSA mortgage conduct rules (1998)**.

---

## 4. How Interest and Principal Are Split Each Month

Every monthly payment is split into two parts:

1. **Interest portion** -- the lender's charge for lending you money.
   This is calculated as: `balance x monthly interest rate`, rounded
   to the nearest penny.
2. **Principal portion** -- the rest of your payment goes toward
   reducing the amount you owe. This is: `monthly payment - interest
   portion`.

### How the Split Changes Over Time

Early in the mortgage, your balance is high, so the interest portion
is large and the principal portion is small. As you gradually pay down
the loan, the balance decreases, so the interest portion gets smaller
and more of each payment goes toward the principal.

For example, on a 200,000 GBP mortgage at 5.25% over 25 years:

| Month | Interest | Principal | Balance Remaining |
|-------|----------|-----------|-------------------|
| 1 | ~875.00 | ~324.62 | ~199,675.38 |
| 12 | ~866.54 | ~333.08 | ~196,813.08 |
| 180 (mid-term) | ~524.44 | ~675.18 | ~129,536.82 |
| 300 (final) | ~7.06 | ~1,192.56 | 0.00 |

These figures are illustrative -- actual values are calculated to the
exact penny.

---

## 5. Early Repayment Penalty

### What Is It?

An **early repayment penalty** (also called an early redemption charge)
is a fee you may have to pay if you repay your mortgage before the end
of the term. This exists because the lender expected to receive a
certain amount of interest income over the fixed-rate period.

### When Does It Apply?

The penalty **only applies** when **all three** conditions are true:

1. You have a **fixed-rate** mortgage (not a variable-rate one)
2. You repay early within the **first 36 months** (3 years) of the
   mortgage
3. There is still an outstanding balance to penalise

### When Is There NO Penalty?

No penalty is charged if:

- You have a **variable-rate** mortgage (rate type = VARIABLE)
- You repay **after month 36** (even on a fixed-rate mortgage)
- You reach the natural end of the mortgage term

### How Much Is the Penalty?

The penalty is **3% of the outstanding balance** at the time of
repayment. For example:

| Outstanding Balance | Penalty (3%) |
|---------------------|--------------|
| 200,000.00 | 6,000.00 |
| 150,000.00 | 4,500.00 |
| 50,000.00 | 1,500.00 |

The penalty is calculated after the normal monthly payment and
interest have been applied for that month.

### Why the Difference Between Fixed and Variable Rates?

**Fixed-rate mortgages:** The lender locks in an interest rate for
the full term. If you repay early, the lender loses the expected
interest income. The penalty compensates for this loss.

**Variable-rate mortgages:** The interest rate can change over time.
The lender's risk profile is different -- rate changes already
absorb some of the risk of early repayment. Therefore, no penalty
is charged.

### Regulatory Basis

This penalty structure is based on the **FSA mortgage conduct rules
(1992)**. The penalty rate was last reviewed on **30 September 2003**.

---

## 6. Input Constraints (Validation Rules)

The calculator checks all inputs before performing any calculations.
If an input is invalid, an error code is returned and no calculation
is performed.

| Input | Minimum | Maximum | Unit | Error Code | Error Name |
|-------|---------|---------|------|------------|------------|
| Principal (loan amount) | 0.01 | 9,999,999.99 | GBP | 1 | INVALID_PRINCIPAL |
| Annual interest rate | 0.000001 | 99.999999 | decimal | 2 | INVALID_RATE |
| Loan term | 1 year | 40 years | years | 3 | INVALID_TERM |
| Repayment month | 1 | term x 12 | months | 4 | INVALID_MONTH |

**Error codes** follow the original COBOL convention:
0 = Success, 1 = Invalid Principal, 2 = Invalid Rate,
3 = Invalid Term, 4 = Invalid Month.

---

## 7. Rate Types

The calculator supports two types of interest rate:

### Fixed Rate (code: F)

- The interest rate stays the same for the entire mortgage term
- Early repayment penalty applies if you repay within the first 36 months
- Suitable for borrowers who want payment certainty

### Variable Rate (code: V)

- The interest rate may change during the mortgage term
- No early repayment penalty applies
- Suitable for borrowers willing to accept rate fluctuation

The rate type is set when the mortgage is created and does not change
during the life of the loan.

---

## 8. Change Log

| Date | Change | Author / Driver |
|------|--------|-----------------|
| 1987-03-14 | Initial implementation | Systems Development Team |
| 1992-11-02 | Added early repayment penalty logic | FSA mortgage conduct rules |
| 1998-06-15 | Updated rounding to comply with FSA rules | FSA rounding standards |
| 2003-09-30 | Added variable rate support | - |
| 2026-05-25 | Migrated from COBOL to Python by COBOL Moderniser | - |

---

## 9. How to Propose a Rule Change

Business rules are stored in three separate files (all containing the
same information in different formats):

| File | Format | Best For |
|------|--------|----------|
| `business_rules.yaml` | YAML | Technical systems, CI/CD pipelines |
| `business_rules.json` | JSON | API integrations, web front-ends |
| `business_rules.md` | Markdown | Human reading, compliance reviews |

### To propose a change:

1. **Open `business_rules.md`** to understand the current rules
2. **Edit `business_rules.yaml`** -- this is the master file that
   the Python calculator reads
3. **Submit the changed YAML file** to the development team with a
   brief explanation of why the change is needed
4. **The development team** will review the change, update the
   corresponding `.md` and `.json` files, run the full test suite
   (226 test cases), and deploy the updated rules

### Common change examples:

- **Penalty rate change**: Edit `penalty_rate` under
  `penalty_rules.early_repayment` (e.g. change 0.03 to 0.02 for 2%)
- **Penalty-free period change**: Edit `repayment_month_max` under
  `penalty_rules.early_repayment.applies_when` (e.g. change 36 to 24)
- **New rate type**: Add a new entry under `rate_types`
- **Maximum term change**: Edit `maximum_years` under
  `validation_rules.term`

### Important notes:

- All monetary values are in **GBP (British Pounds)**
- All interest rates are expressed as **decimals** (5.25% = 0.0525)
- Changes to validation limits may require updating test cases
- Any penalty rule change requires compliance sign-off before deployment

---

*Document generated by COBOL Moderniser -- Agent 7 (Externaliser).*
*Version: 1.0.0*
