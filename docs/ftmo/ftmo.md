# FTMO Trading Objectives & Rules

---

## 1. Maximum Loss (Max Loss)

Before you can trade on a demo FTMO Account, we need to see how you can manage risk. Because of this, we have developed **Trading Objectives**. There are four basic Trading Objectives you need to know to become an FTMO Trader and trade up to $200,000 on your demo FTMO Account. The third rule is called **Maximum Loss**.

### Overview

The calculation of the Maximum Loss is similar to the Maximum Daily Loss. The only difference is that **it is not limited to one day, but spans the entire duration of the testing period**.

We have developed this rule to protect our capital while guiding clients and FTMO Traders to maintain strict money and risk management discipline.

> **Key Takeaway:**
>
> - This rule acts as the **account Stop Loss**.
> - Equity on your trading account **must not drop below 90% of the initial account balance** at any given time during the account duration.
> - You **cannot lose more than 10%** of your initial balance overall.

### Calculation Details

- **Equity vs. Balance:** The calculation uses **account equity**, not balance.
  - _Balance_ only reflects closed positions.
  - _Equity_ includes floating profits and losses from open trades, as well as commissions and swaps.
- **Rule Consistency:** The rule remains identical across all three stages (e.g., with a **$100,000 account**, your equity can **never drop below $90,000**).

> **Example:**  
> If your balance is **$92,000** and you have a floating loss of **$2,001**, your equity is **$89,999** (below $90,000). The limit is exceeded and the rule is violated!

This 10% breathing space provides traders with sufficient room to demonstrate strategy suitability during the Evaluation Process while serving as a safety buffer during drawdown periods.

---

## 2. Maximum Daily Loss (MDL)

Before trading on a demo FTMO Account, risk management capabilities must be verified through the **Maximum Daily Loss** rule.

### Table of Contents

1. [What is Maximum Daily Loss?](#what-is-maximum-daily-loss)
2. [How is the Limit Calculated?](#how-is-the-limit-calculated)
3. [What is Included in the Calculation?](#what-is-included-in-the-calculation)
4. [Overnight Positions & Timezone Notice](#overnight-positions--timezone-notice)
5. [Example Calculation ($100,000 Account)](#example-calculation-100000-account)
6. [Why This Rule Matters](#why-this-rule-matters)

---

### What is Maximum Daily Loss?

The **Maximum Daily Loss Limit** defines the exact baseline below which your equity cannot drop at any point during a trading day.

Depending on your selected account structure:

- **2-Step FTMO Challenge:** Set at **5%** of the Initial Simulated Capital.
- **1-Step FTMO Challenge:** Set at **3%** of the Initial Simulated Capital.

---

### How is the Limit Calculated?

The limit is recalculated every day at **midnight CE(S)T** using the following formula:

```text
Daily Loss Limit = Account balance at midnight CE(S)T of previous day - 5% of Initial Simulated Capital
```

> **Important Notes:**
>
> - On **Day 1**, the balance used for calculation is the **Initial Simulated Capital**.
> - The daily loss limit dynamic baseline **increases or decreases** based on the balance recorded at midnight CE(S)T.

---

### What is Included in the Calculation?

The rule is evaluated continuously against **Equity**. The calculation incorporates:

- Closed trade results (realized P/L).
- Floating profits/losses of open positions (unrealized P/L).
- Broker commissions and swap fees.

---

### Overnight Positions & Timezone Notice

If you hold positions overnight, exercise caution:

- The Maximum Daily Loss limit resets **every midnight CE(S)T** based on the balance recorded at that exact timestamp.
- A position that was safely within limits before midnight **may trigger a violation after the reset** if floating losses remain large relative to the new daily baseline.

_(Tip: Visit the Timezone Converter in the FTMO Client Area to check the exact reset time in your local timezone.)_

---

### Example Calculation ($100,000 Account)

_Initial Simulated Capital = **$100,000** | Daily Limit Buffer = 5% ($5,000)_

#### **Day 1**

- **Initial Capital:** $100,000
- **Calculation:** $100,000 - $5,000 = $95,000
- **Limit for Day 1:** **$95,000**

#### **Day 2**

- **Balance at Midnight CE(S)T:** $102,000 _(+2% profit on Day 1)_
- **Calculation:** $102,000 - $5,000 = $97,000
- **Limit for Day 2:** **$97,000**

#### **Day 3**

- **Balance at Midnight CE(S)T:** $101,000 _(-1% loss on Day 2)_
- **Calculation:** $101,000 - $5,000 = $96,000
- **Limit for Day 3:** **$96,000**

#### **Summary Table**

| Day       | Balance at 00:00 CE(S)T | Previous Day Change  | Limit Calculation ($100k - $5k Buffer) | Minimum Allowed Equity | Mathematical Status |
| :-------- | :---------------------- | :------------------- | :------------------------------------- | :--------------------- | :------------------ |
| **Day 1** | $100,000                | Initial Capital      | $100,000 - $5,000                      | **$95,000**            | 100% Accurate       |
| **Day 2** | $102,000                | Profit +$2,000 (+2%) | $102,000 - $5,000                      | **$97,000**            | 100% Accurate       |
| **Day 3** | $101,000                | Loss -$1,000 (-1%)   | $101,000 - $5,000                      | **$96,000**            | 100% Accurate       |

---

### Why This Rule Matters

The Maximum Daily Loss rule defines daily operational risk limits and fosters long-term consistency in risk management practices across both the Evaluation Process and funded FTMO Accounts.

---

## 3. FTMO Swing Account Leverage Specifications

Currently, **FTMO Swing** accounts feature different leverage levels depending on the asset class, rather than a single unified rate:

| Asset Class            | Current Swing Leverage |
| ---------------------- | ---------------------: |
| **Forex**              |               **1:30** |
| **Indices**            |               **1:15** |
| **XAUUSD / XAU pairs** |               **1:15** |
| Commodities            |                    1:1 |
| Crypto / Equity CFDs   |                    1:1 |

Specifically for **XAUUSD**, FTMO increased the Swing leverage from **1:9 → 1:15** effective from **February 1, 2026**. Standard accounts currently offer **1:50** leverage for XAUUSD. ([FTMO.com](https://ftmo.com/en/blog/trading-updates/trading-update-2-feb-2026/?utm_source=chatgpt.com))

Therefore, when trading on **FTMO Swing**:

> **XAUUSD = 1:15**

And when trading **EURUSD / GBPUSD**:

> **Forex = 1:30**

*Note: Leverage **does not alter the profit/loss per 1 lot**; it primarily adjusts the **margin required to open a position**. For instance, if XAUUSD moves $10 on a 1 lot position, the P&L remains approximately ±$1,000 regardless of whether leverage is 1:15 or 1:50.* ([FTMO — Trading Update 2 Feb 2026](https://ftmo.com/en/blog/trading-updates/trading-update-2-feb-2026/?utm_source=chatgpt.com))

