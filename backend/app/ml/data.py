"""Synthetic labeled ticket dataset for the urgency/category classifier.

No public fintech ticket dataset exists (see TRD section 4), so this module
hand-authors template sentences per (category, urgency) combination and
multiplies them with placeholder substitution to produce a few hundred
labeled examples — a stand-in for the "hand-written or LLM-drafted" fintech
examples the TRD calls for.
"""

import random
from dataclasses import dataclass

CATEGORIES = ["payment_failure", "refund_delay", "account_lock", "dispute", "general_query"]
URGENCY_LEVELS = ["low", "medium", "high"]

_AMOUNTS = ["$12.50", "$45", "$99.99", "$230", "$1,200", "$15", "$68.20", "$500"]
_DAYS = ["2", "3", "5", "7", "10", "14"]
_ORDER_IDS = ["#48213", "#A1092", "#77281", "#9910", "#33456"]
_MERCHANTS = ["a local store", "an online retailer", "a subscription service", "a marketplace seller"]

# (category, urgency) -> template sentences with {amount}/{days}/{order_id}/{merchant} placeholders
_TEMPLATES: dict[tuple[str, str], list[str]] = {
    ("payment_failure", "high"): [
        "URGENT: I see a charge on my account I did NOT make, someone charged {amount} using my card and I think my account was hacked!",
        "My card was charged {amount} twice within minutes and I need this fixed immediately, this looks like fraud.",
        "I think someone stole my card info, there's a suspicious payment on my account and money is missing, please help right now.",
        "This is urgent — my rent payment of {amount} failed and now my account shows a hold I don't recognize, I'm worried about fraud.",
        "Emergency: a payment for {amount} failed but I was still charged, and I don't recognize this transaction at all.",
    ],
    ("payment_failure", "medium"): [
        "My payment of {amount} failed at checkout and I'm not sure why, can you help me figure out what happened?",
        "I tried to pay {amount} for {merchant} but it keeps failing, my card should have enough funds.",
        "Payment for order {order_id} did not go through, the app just says 'failed'.",
        "I got a payment failure notice for {amount}, but I'm not sure if I was actually charged or not.",
    ],
    ("payment_failure", "low"): [
        "Quick question — why do payments sometimes fail even when there's enough money in the account?",
        "Just curious what the retry policy is when a payment fails.",
        "Wondering if failed payments show up as pending charges on my bank statement.",
    ],
    ("refund_delay", "high"): [
        "It has been {days} days and my refund of {amount} still hasn't arrived, I need this money urgently for bills.",
        "This refund delay is unacceptable, {amount} was supposed to be refunded weeks ago and I'm struggling without it.",
        "I am extremely frustrated, my {amount} refund from order {order_id} is way overdue and no one has explained why.",
    ],
    ("refund_delay", "medium"): [
        "My refund of {amount} for order {order_id} hasn't shown up yet after {days} days, can you check the status?",
        "I was told my refund would arrive within {days} business days but it's been longer, what's going on?",
        "Can you tell me the status of my {amount} refund from {merchant}?",
    ],
    ("refund_delay", "low"): [
        "How long do refunds usually take to process?",
        "Just wondering when I should expect a refund to show up after it's approved.",
        "Does a refund go back to my card or as store credit?",
    ],
    ("account_lock", "high"): [
        "My account just got locked and I can't access my money at all, this is urgent, I need to pay bills today!",
        "I think my account was locked due to fraud, someone may have tried to log in, please help immediately.",
        "URGENT: locked out of my account with no explanation, I have an emergency and need access right now.",
    ],
    ("account_lock", "medium"): [
        "My account got locked after a few failed login attempts, how do I unlock it?",
        "I'm locked out of my account, can you tell me why and how to fix it?",
        "The app says my account is locked pending review, how long will that take?",
    ],
    ("account_lock", "low"): [
        "How can I avoid getting my account locked in the future?",
        "Just curious what usually causes an account lock.",
        "Does enabling two-factor authentication help prevent lockouts?",
    ],
    ("dispute", "high"): [
        "I need to dispute a charge of {amount} immediately, I never authorized this transaction and I'm worried about more fraud!",
        "This is urgent, there's a fraudulent charge of {amount} on my account from {merchant} that I did not make.",
        "Please help right away, I see an unauthorized charge of {amount} and need to dispute it before more damage is done.",
    ],
    ("dispute", "medium"): [
        "I want to dispute a charge of {amount} from {merchant}, the item never arrived.",
        "How do I file a dispute for order {order_id}? I was charged the wrong amount.",
        "I'd like to start a dispute for a {amount} charge I don't recognize.",
    ],
    ("dispute", "low"): [
        "What's the process for disputing a transaction?",
        "How long do disputes usually take to resolve?",
        "Just wondering if I get my money back automatically during a dispute.",
    ],
    ("general_query", "high"): [
        "I urgently need to update my phone number because I lost access to my old one and can't log in!",
        "This is time-sensitive, I need to change my email today before an important payment goes through.",
    ],
    ("general_query", "medium"): [
        "How do I update my mailing address on the account?",
        "Can you explain the monthly fee of {amount} on my statement?",
        "I'm having trouble logging into the app, can you help?",
    ],
    ("general_query", "low"): [
        "Just wondering how to contact support for general questions.",
        "What's the best way to update my profile information?",
        "Curious about typical response times for support tickets.",
    ],
}

_VARIATIONS_PER_TEMPLATE = 6


@dataclass(frozen=True)
class TicketExample:
    text: str
    category: str
    urgency: str


def generate_dataset(seed: int = 42) -> list[TicketExample]:
    rng = random.Random(seed)
    examples: list[TicketExample] = []

    for (category, urgency), templates in _TEMPLATES.items():
        for template in templates:
            for _ in range(_VARIATIONS_PER_TEMPLATE):
                text = template.format(
                    amount=rng.choice(_AMOUNTS),
                    days=rng.choice(_DAYS),
                    order_id=rng.choice(_ORDER_IDS),
                    merchant=rng.choice(_MERCHANTS),
                )
                examples.append(TicketExample(text=text, category=category, urgency=urgency))

    rng.shuffle(examples)
    return examples
