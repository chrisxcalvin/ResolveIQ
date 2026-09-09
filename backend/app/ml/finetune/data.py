"""Synthetic (ticket, context, grounded reply) examples for LoRA fine-tuning
the cheap-tier drafting model.

Each entry pairs several ticket phrasings with one hand-written grounded
reply tied to a specific KB article — the same structure the model will see
at inference time (ticket + retrieved context -> grounded reply citing the
source). Demonstration-scale, same honestly-synthetic framing as the rest of
this project's data (TRD section 4).
"""

from dataclasses import dataclass

from app.kb.embed import ARTICLES_DIR, _parse_article

# article filename -> (ticket phrasings, hand-written grounded reply)
_EXAMPLES: dict[str, tuple[list[str], str]] = {
    "payment_failure_common_reasons.md": (
        [
            "why did my payment fail? i have plenty of money in my account",
            "my card got declined for no reason, whats going on",
            "payment failed but i know i have enough funds, please explain",
            "getting a decline every time i try to pay, why",
        ],
        "Most failed payments come down to one of a few things: insufficient funds, "
        "an expired or mistyped card, the bank declining for its own risk reasons, "
        "or our fraud system flagging it for review. No funds are actually taken "
        "when a payment fails — nothing is charged until a transaction fully "
        "clears. If your bank gave a generic decline reason, they'll have more "
        "detail on why than we do, so it's worth giving them a quick call. "
        "(Source: Why Payments Fail — Common Reasons)",
    ),
    "payment_failure_retry_policy.md": (
        [
            "will my failed payment be retried automatically or do i need to redo it",
            "how many times will you retry a failed payment",
            "should i manually resubmit after a payment fails",
            "does a failed payment retry itself or is it gone for good",
        ],
        "When a scheduled payment fails, it's automatically retried up to three "
        "times over five days — at 24, 72, and 120 hours. You don't need to "
        "resubmit manually; doing so can actually cause a duplicate charge if a "
        "retry succeeds around the same time. If all three retries fail, you'll "
        "need to submit payment manually with an updated method. "
        "(Source: Failed Payment Retry Policy)",
    ),
    "payment_failure_duplicate_charge.md": (
        [
            "i think i got charged twice for the same thing",
            "why do i see two charges for one purchase",
            "double charged, need this fixed",
            "there are two identical charges on my account, is that normal",
        ],
        "Duplicate charges usually happen when a slow page reload causes a "
        "second payment attempt. First, check whether both charges actually "
        "settled or if one is just a pending authorization hold — holds aren't "
        "real charges and clear on their own within 3-5 business days. If both "
        "truly settled, the duplicate should be refunded within 2 business days. "
        "(Source: Troubleshooting a Duplicate or Double Charge)",
    ),
    "payment_failure_authorization_hold.md": (
        [
            "the app says my payment failed but my bank shows the money is gone",
            "why is money missing from my account if the payment failed",
            "payment failed but funds are still on hold, whats happening",
            "my bank shows a hold even though the app says the payment didnt go through",
        ],
        "That's an authorization hold, not an actual charge — it's a temporary "
        "reservation your bank placed before the payment was ultimately declined "
        "on our end. No money has moved. Holds are released automatically by "
        "your bank, typically within 3-5 business days; we can't force it to "
        "release early. (Source: Payment Failed But Funds Are Still Held)",
    ),
    "refund_delay_standard_timeline.md": (
        [
            "how long does a refund usually take",
            "when will my refund show up",
            "whats the normal refund processing time",
            "how many days until i see my refund",
        ],
        "Once approved, we release the refund back to your original payment "
        "method within 1 business day. From there it typically takes 5-10 "
        "business days for card refunds or 3-5 business days for bank transfers "
        "to actually appear, depending on your bank. If it's been more than 10 "
        "business days since approval, that's outside the normal window and "
        "worth escalating. (Source: Standard Refund Processing Timeline)",
    ),
    "refund_delay_beyond_window.md": (
        [
            "its been way longer than expected for my refund, why",
            "my refund is late, what could be causing that",
            "refund is delayed past the usual timeframe, help",
            "why hasnt my refund arrived when it should have by now",
        ],
        "A few things can push a refund past the normal window: the original "
        "card was closed or replaced, the refund got a routine fraud/compliance "
        "recheck, or your bank is just slow to post it. If your card expired, "
        "most networks will still route the refund to the replacement card, but "
        "that can add a few extra days. "
        "(Source: Why a Refund Might Be Delayed Beyond the Standard Window)",
    ),
    "refund_delay_checking_status.md": (
        [
            "can you check the status of my refund",
            "whats the current status on my refund request",
            "is my refund pending or already sent",
            "can you give me an update on where my refund is",
        ],
        "Refunds move through three states: pending (approved, not yet sent), "
        "sent (released to your bank, awaiting posting), or completed (confirmed "
        "posted). If it's showing 'sent,' the funds have already left our system "
        "and the remaining timing is entirely up to your bank — we won't have "
        "visibility into the exact arrival date at that point. "
        "(Source: How to Check Refund Status)",
    ),
    "refund_delay_original_method_vs_credit.md": (
        [
            "can i get my refund as cash instead of back to my card",
            "can you send my refund to a different account",
            "why cant i choose how i get refunded",
            "can my refund go to my other card instead",
        ],
        "By card network policy, refunds always go back to the original payment "
        "method used for the purchase — we can't redirect it to a different "
        "card, account, or store credit unless that original method no longer "
        "exists. If it's been closed, we'd issue a statement credit or, for bank "
        "transfers, need you to confirm a new destination account. "
        "(Source: Refund to Original Payment Method vs. Statement Credit)",
    ),
    "account_lock_common_reasons.md": (
        [
            "why is my account locked",
            "what caused my account to get locked",
            "no idea why im locked out, can you explain",
            "my account just locked itself, why would that happen",
        ],
        "Accounts get locked automatically for one of three reasons: several "
        "consecutive failed login attempts, login activity from an unrecognized "
        "device combined with other risk signals, or a routine compliance "
        "review. It's a protective measure, not a penalty — meant to stop "
        "unauthorized access before it happens. "
        "(Source: Common Reasons Accounts Get Locked)",
    ),
    "account_lock_self_service_unlock.md": (
        [
            "how do i unlock my own account",
            "is there a way to unlock this myself without waiting",
            "can i self-verify to get back into my account",
            "whats the fastest way to get unlocked",
        ],
        "For locks caused by failed logins or a new-device flag, you can "
        "usually self-unlock in the app by confirming a one-time code sent to "
        "your registered email or phone, plus your date of birth. This option "
        "isn't available if the lock was triggered by a suspected fraud signal "
        "or compliance review — those need manual review first. "
        "(Source: How to Unlock Your Account — Self-Service Steps)",
    ),
    "account_lock_compliance_review.md": (
        [
            "my account is locked for some kind of review, how long will that take",
            "locked for compliance check, whats the timeline",
            "why do i need a compliance review just to use my account",
            "how long do compliance locks usually last",
        ],
        "Some locks come from routine compliance requirements rather than "
        "anything suspicious about you specifically — periodic identity "
        "re-verification, for example. These are handled by a dedicated "
        "compliance team and typically take 1-3 business days; support can't "
        "expedite it directly. No action is needed from you unless compliance "
        "reaches out requesting documents. "
        "(Source: Account Locked for Compliance/KYC Review)",
    ),
    "account_lock_preventing_lockouts.md": (
        [
            "how do i stop this from happening again",
            "any tips to avoid getting locked out in the future",
            "whats the best way to prevent future lockouts",
            "how can i avoid this happening next time",
        ],
        "The most common preventable cause is a browser auto-filling an old, "
        "outdated password after you've changed it — updating your saved "
        "password in your browser helps a lot. Enabling two-factor "
        "authentication also reduces new-device lockouts, and keeping your "
        "registered email/phone current is the single most important thing, "
        "since both self-service unlock and recovery depend on reaching you "
        "there. (Source: Preventing Future Account Lockouts)",
    ),
    "dispute_how_to_file.md": (
        [
            "how do i dispute a charge",
            "i dont recognize this transaction, how do i dispute it",
            "whats the process to file a dispute",
            "how do i start a dispute for a charge",
        ],
        "To file a dispute, we'll need the transaction date, amount, and a "
        "short description of the issue — this opens a formal investigation "
        "with the card network. It's worth trying to resolve it directly with "
        "the merchant first if possible, since a merchant refund is faster and "
        "skips the investigation process entirely. "
        "(Source: How to File a Transaction Dispute)",
    ),
    "dispute_investigation_timeline.md": (
        [
            "how long does a dispute take to resolve",
            "whats the timeline once i file a dispute",
            "how soon will my dispute be decided",
            "how many days does the dispute process take",
        ],
        "Once filed, the card network gives the merchant a chance to respond, "
        "so the full process typically takes 30-45 days, though simple cases "
        "can resolve faster. You may be asked for extra documentation along the "
        "way — responding promptly to those requests is the biggest factor in "
        "avoiding extra delay. "
        "(Source: Dispute Investigation Timeline and Process)",
    ),
    "dispute_provisional_credit.md": (
        [
            "do i get my money back right away when i dispute a charge",
            "will i get a temporary credit while the dispute is being investigated",
            "is the refund immediate for a dispute",
            "do i get credited before the dispute is finished",
        ],
        "For many dispute types, we issue a provisional credit for the "
        "disputed amount while the investigation is ongoing, so you're not out "
        "of funds during the 30-45 day process. It's temporary, though — if the "
        "dispute is ultimately decided in the merchant's favor, that credit is "
        "reversed and the charge stands. "
        "(Source: Provisional Credit During a Dispute)",
    ),
    "dispute_outcomes.md": (
        [
            "i lost my dispute, can i appeal",
            "what happens if the dispute doesnt go my way",
            "can you tell me why my dispute was denied",
            "is a dispute decision final or can it be reversed",
        ],
        "If a dispute is decided in your favor, any provisional credit becomes "
        "permanent automatically. If it's decided against you, the provisional "
        "credit is reversed and the original charge stands — card network "
        "decisions are generally final, though rare new evidence can "
        "occasionally prompt a re-investigation. I can share the specific "
        "reason the network gave, if one is available. "
        "(Source: Dispute Outcomes — What Happens If You Win or Lose)",
    ),
    "general_query_update_account_info.md": (
        [
            "how do i update my email on file",
            "can i change my phone number in the app",
            "how do i update my address",
            "how do i change my name on the account",
        ],
        "Most account details — name, email, phone, and address — can be "
        "updated directly in the app under Account Settings; changing your "
        "email or phone requires confirming a one-time code sent to the new "
        "contact method. A legal name change needs a supporting document "
        "upload instead, since it has to match your identity verification "
        "records. (Source: How to Update Your Account Information)",
    ),
    "general_query_statement_and_fees.md": (
        [
            "can you explain a fee on my statement",
            "why was i charged a monthly fee",
            "when do my statements come out",
            "whats this fee on my account for",
        ],
        "Statements generate monthly on the same calendar day as your "
        "account's original opening date, viewable in the app under "
        "Statements. Common fees include a monthly maintenance fee (waived if "
        "you meet a minimum balance or activity threshold), foreign "
        "transaction fees, and occasional one-time fees like expedited card "
        "replacement — worth double-checking whether a waiver condition was "
        "actually met before assuming a fee is correct. "
        "(Source: Understanding Your Statement and Fees)",
    ),
    "general_query_contacting_support.md": (
        [
            "whats the best way to reach support",
            "how long does support usually take to respond",
            "do i need to email and chat both to get a faster answer",
            "how fast do you usually reply to tickets",
        ],
        "You can reach support through in-app chat, email, or social channels "
        "— they all feed into the same ticket queue, so your history carries "
        "over regardless of which one you use. Standard response time is "
        "within 1 business day, and high-urgency issues like suspected fraud "
        "or account lockouts get prioritized faster. Reaching out on multiple "
        "channels for the same issue actually slows things down since "
        "duplicate tickets need to be manually merged. "
        "(Source: How to Contact Support and Expected Response Times)",
    ),
    "general_query_app_login_troubleshooting.md": (
        [
            "the app wont let me log in, whats wrong",
            "im getting an error when i try to log in",
            "login isnt working, any idea why",
            "cant sign into the app, what should i check",
        ],
        "Most login issues come down to a typo'd email or an outdated app "
        "version losing compatibility with current login security — updating "
        "the app and double-checking your registered email usually resolves "
        "it. If you're seeing a generic 'something went wrong' error rather "
        "than an explicit invalid-password message, it's more likely a "
        "network or app-version issue than an account lock. "
        "(Source: Mobile App and Login Troubleshooting)",
    ),
}


@dataclass(frozen=True)
class FinetuneExample:
    ticket_text: str
    context: str
    reply: str


def generate_finetune_examples() -> list[FinetuneExample]:
    examples: list[FinetuneExample] = []

    for filename, (tickets, reply) in _EXAMPLES.items():
        _, _, context = _parse_article(ARTICLES_DIR / filename)
        for ticket_text in tickets:
            examples.append(FinetuneExample(ticket_text=ticket_text, context=context, reply=reply))

    return examples
