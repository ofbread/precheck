"""Precheck: decide what, if anything, a fact-checker should check in a user's input."""
import json
import os
import re
from dataclasses import dataclass, field

from .prompt import load

PROMPT, PROMPT_HASH = load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "precheck.md"))

# The action each operation belongs to. 
ACTIONS = {
    "verify": "verify",
    "extract": "verify",
    "decompose": "verify",
    "add_reference_time": "verify",
    "propose_claim": "clarify",
    "clarify": "clarify",
}

# How one clarification turn is shown to the model under "Conversation so far".
TURN = 'You proposed to check: "{proposed}"\nThe user replied: "{correction}"'

_PLACEHOLDER = re.compile(r"\s*,?\s*(?:\bas of\b\s*)?\[[^\]\n]*"
                          r"(?:date|year|time|month|day|current|reference|specific|name)[^\]\n]*\]", re.I)


def strip_placeholders(text):
    """Remove placeholders the model writes instead of a real value, such as "[date]" or"as of [current year]". """
    text = _PLACEHOLDER.sub("", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)  
    return " ".join(text.split()).strip()


def parse_json(reply):
    """Return the JSON object in the model's reply, or None."""
    match = re.search(r"\{.*\}", reply or "", re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except ValueError:
            return None
    return None


def _text(value):
    """Return a reply field as a string; None, "null" and "none" become ""."""
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.lower() in ("null", "none") else value


@dataclass
class Decision:
    """One decision about an input, returned by `Precheck.decide()`."""

    operation: str         # verify, extract, decompose, add_reference_time, propose_claim, clarify or abstain
    action: str            # verify, clarify, decline or defer
    claim: str             # the claim to check, or "" if there is none
    atoms: list            # the separate claims, for decompose
    question: str          # the question for the user, or ""
    reason: str            # why there is no claim to check, for abstain
    reply: dict            # the model's parsed JSON reply, or {} if it could not be parsed


@dataclass
class Elicitation:
    """The outcome of a clarification loop, returned by Precheck.elicit()."""

    claim: str             # the claim to check after the dialogue
    confirmed: bool        # whether the user confirmed the last proposed claim
    turns: list = field(default_factory=list)      # (proposed claim, correction) for each turn
    readings: list = field(default_factory=list)   # the claim before any question, then after each turn
    decisions: list = field(default_factory=list)  # every Decision made, starting with the first


def action_of(reply):
    operation = _text(reply.get("action")).lower()
    if operation == "abstain":
        reason = _text(reply.get("abstain_reason")).lower()
        return "defer" if reason == "forecast_not_yet" else "decline"
    return ACTIONS.get(operation, "verify")


class Precheck:
    """Decides what a fact-checker should check in a user's input."""

    prompt_hash = PROMPT_HASH

    def __init__(self, llm):
        self.llm = llm

    def decide(self, text, history=""):
        """Return a Decision for `text`. `history` is the clarification dialogue so far, if any."""
        prompt = PROMPT.replace("{input}", text).replace("{history}", history)
        reply = parse_json(self.llm(prompt)) or {}
        atoms = reply.get("check_atoms")
        return Decision(
            operation=_text(reply.get("action")).lower(),
            action=action_of(reply),
            claim=strip_placeholders(_text(reply.get("check_claim"))),
            atoms=[_text(a) for a in atoms if _text(a)] if isinstance(atoms, list) else [],
            question=_text(reply.get("confirm_question")),
            reason=_text(reply.get("abstain_reason")).lower(),
            reply=reply)

    def elicit(self, text, ask, max_turns=3, always_ask=False):
        """Run the clarification loop on `text` and return an Elicitation.

        `ask(claim, question)` shows the user the proposed claim and the question. It returns None
        if the user confirms the claim, or the user's correction as a string.
        """
        decision = self.decide(text)
        result = Elicitation(claim=decision.claim, confirmed=False, readings=[decision.claim], decisions=[decision])
        if decision.action != "clarify" and not always_ask:
            if decision.action != "verify":
                result.claim = ""
            return result
        history = []
        while len(result.turns) < max_turns:
            proposed = decision.claim or text
            correction = ask(proposed, decision.question)
            if correction is None:
                result.claim, result.confirmed = proposed, True
                return result
            correction = correction.strip()
            if not correction:
                break
            result.turns.append((proposed, correction))
            history.append(TURN.format(proposed=proposed, correction=correction))
            decision = self.decide(text, "\n".join(history))
            result.decisions.append(decision)
            result.readings.append(decision.claim or result.readings[-1])
            if result.readings[-1] == proposed:
                break  
        result.claim = result.readings[-1]
        return result
