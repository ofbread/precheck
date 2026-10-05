# precheck

Precheck is an interactive claim elicitation framework for automated fact-checking. It runs
before evidence retrieval and decides what, if anything, a fact-checker should check in a
user's input.

Not everything people send to a fact-checker is a clean claim. Many inputs are questions,
opinions, forecasts or half-formed claims. Precheck reads the input and takes one of four
actions:

| Action | When | Operations | Output |
|---|---|---|---|
| verify | the input holds a checkable claim | `verify`, `extract`, `decompose`, `add_reference_time` | the claim to check |
| clarify | a question, a false premise, or a claim whose meaning only the user can settle | `propose_claim`, `clarify` | a proposed claim and a question for the user |
| decline | an opinion, advice, or no claim at all | `abstain` | the reason |
| defer | a forecast whose outcome is not known yet | `abstain` (`forecast_not_yet`) | the reason |

When the action is clarify, Precheck shows the user the claim it proposes to check. The user
confirms or corrects it, and Precheck reads the input again with the correction, for up to
three turns. The claim it settles on is what you pass to your fact-checker.

## Installation

```bash
git clone https://github.com/ofbread/precheck
cd precheck
pip install -e .
```

Precheck needs Python 3.9 or later.

## Usage

Precheck works with any model behind an OpenAI-compatible API. For example, with a local vLLM
server:

```bash
vllm serve Qwen/Qwen2.5-32B-Instruct --served-model-name qwen32b --port 8000
```

### Making a decision

```python
from precheck import Precheck, openai_compatible

precheck = Precheck(openai_compatible("http://127.0.0.1:8000/v1", "qwen32b"))

decision = precheck.decide("Did the city council ban plastic bags last year?")
print(decision.action)    # verify, clarify, decline or defer
print(decision.claim)     # the claim to check
print(decision.question)  # the question for the user, if the action is clarify
```

For a hosted API, pass your key: `openai_compatible(url, model, api_key="...")`.

### Running the clarification loop

`elicit()` takes an `ask` function, which is your interface to the user. It receives the
proposed claim and the question, and returns `None` if the user confirms the claim, or the
user's correction as a string.

```python
def ask(claim, question):
    print(f"I will check: {claim}")
    answer = input(f"{question} (press Enter to confirm, or type a correction) ")
    return answer or None

result = precheck.elicit("Did the city council ban plastic bags last year?", ask)
if result.claim:
    print("Check:", result.claim)
else:
    first = result.decisions[0]
    print("Nothing to check:", first.action, first.reason)
```

`elicit()` only asks the user when the first decision is clarify. For verify it returns the
claim right away, and for decline and defer it returns an empty claim.

### Using another model API

`Precheck` accepts any function that takes the prompt text and returns the model's reply as a
string:

```python
def my_llm(prompt):
    ...  # call your model and return its reply

precheck = Precheck(my_llm)
```

## Output

`decide()` returns a `Decision`:

| Field | Description |
|---|---|
| `action` | `verify`, `clarify`, `decline` or `defer` |
| `operation` | one of the seven operations above |
| `claim` | the claim to check, or `""` if there is none |
| `atoms` | the separate claims, for `decompose` |
| `question` | the question for the user, or `""` |
| `reason` | why there is nothing to check, for `abstain`: `opinion`, `advice`, `non_claim`, `forecast_not_yet`, `unanswerable_in_principle` or `missing_context` |
| `reply` | the model's parsed JSON reply, or `{}` if it could not be parsed (the action then falls back to `verify`) |

`elicit()` returns an `Elicitation`:

| Field | Description |
|---|---|
| `claim` | the claim to check at the end of the dialogue (`""` for decline and defer) |
| `confirmed` | whether the user confirmed it |
| `turns` | a `(proposed claim, correction)` pair for each turn |
| `readings` | the claim before the first question, then after each turn |
| `decisions` | every `Decision` made, starting with the first |

## License

Apache-2.0. See [LICENSE](LICENSE).
