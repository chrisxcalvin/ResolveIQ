---
title: Failed Payment Retry Policy
category: payment_failure
---

When a scheduled payment fails, our system automatically retries the
charge up to three times over five days: the first retry happens after
24 hours, the second after 72 hours, and the third after 120 hours.

Customers do not need to manually retry a payment during this window —
doing so can result in a duplicate charge if the original retry succeeds
around the same time. If all three automatic retries fail, the payment
moves to a permanently failed state and the customer must resubmit
payment manually with an updated payment method.

Retries are paused automatically if the customer updates their payment
method before the next scheduled retry — the updated method is used for
the next attempt instead.
